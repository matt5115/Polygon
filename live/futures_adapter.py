#!/usr/bin/env python3
"""live/futures_adapter.py
Phase-1 tranche engine for CME Micro-Bitcoin Futures (MBT) based on the
rules declared in ``config/futures_rules.yaml``.

Responsibilities implemented in this phase:
1. Load YAML rules (symbol, contract, engine params, tranche details).
2. Poll Ironbeam REST endpoint to keep ``self.pos`` (net contracts) up to date.
3. Consume Ironbeam market-data WebSocket and update ``self.price``.
4. For each *active* tranche
   • ``scalp_add`` – once qty is filled, ensure its OCO (tp1, tp2, stop)
     reduce-only orders exist; recreate any that are missing.
   • ``core_runner`` – once qty is filled, ensure initial trailing stop and
     hard-target limit orders exist.
5. Obey ``position_limit`` hard guard.

Trailing ATR logic is deferred to the next phase.

All network I/O (REST + WS) is async via ``aiohttp`` and ``websockets``.
Unit-tests can monkey-patch ``_fetch_open_orders`` and ``IBClient.submit_order``
so no external calls are made.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List
from collections import deque
import statistics
from typing import Any, Dict, List

import aiohttp
import websockets
import yaml

from live.ib_order import IBClient, TICK_SIZE  # pylint: disable=import-error

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_YAML = ROOT / "config" / "futures_rules.yaml"

LOGGER = logging.getLogger("FutAd")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")

# ---------------------------------------------------------------------------
# FuturesAdapter (tranche engine)
# ---------------------------------------------------------------------------

class FuturesAdapter:  # pylint: disable=too-many-instance-attributes
    """Async tranche engine implementing fixed OCO/stop logic."""

    # ------------------------------------------------------------------
    # Construction / cfg load
    # ------------------------------------------------------------------

    def __init__(self, rules_path: str | os.PathLike = DEFAULT_RULES_YAML, poll_sec: int | None = None):
        self.cfg: Dict[str, Any] = yaml.safe_load(Path(rules_path).read_text())
        self.tranches: Dict[str, Dict[str, Any]] = {t["name"]: t for t in self.cfg["tranches"]}

        self.symbol_root: str = self.cfg["symbol"]
        self.contract: str = self.cfg["contract"]
        self.rest_poll_sec: int = poll_sec or int(self.cfg["engine"]["poll_sec"])
        self.ws_url: str = self.cfg["engine"]["md_ws"]
        self.position_limit: int = int(self.cfg["position_limit"])

        self.ib = IBClient()

        # mutable state ------------------------------------------------
        self.pos: int = 0  # net contracts (negative == short)
        self.price: float | None = None  # last trade price

        # trailing-stop state ----------------------------------------
        self._close_buf: deque[float] = deque(maxlen=900)  # 15m of seconds
        self._bars_1m: deque[Dict[str, float]] = deque(maxlen=15)
        self._last_bar_min: int | None = None

        self._core_stop_id: str | None = None
        self._core_stop_px: float | None = None

        # mapping of required legs -> cached orderId (populated by reconcile)
        self.legs_required: Dict[str, Dict[str, str | None]] = {
            "scalp_add": {"tp1": None, "tp2": None, "stop": None},
            "core_runner": {"stop": None, "tgt1": None, "tgt2": None},
        }

        # ------------------------------------------------------------------
        # External entry points
        # ------------------------------------------------------------------

    def attach(self) -> None:
        """Blocking helper used by trade_daemon – starts the asyncio tasks."""
        try:
            asyncio.run(self._main())
        except KeyboardInterrupt:
            LOGGER.info("FuturesAdapter stopped via Ctrl-C")

    # ------------------------------------------------------------------
    # Top-level async orchestration
    # ------------------------------------------------------------------

    async def _main(self) -> None:  # noqa: D401 (imperative name clearer)
        await asyncio.gather(self._poll_positions(), self._md_loop())

    # ------------------------------------------------------------------
    # Position polling – REST every *poll_sec*
    # ------------------------------------------------------------------

    async def _poll_positions(self) -> None:
        path = "/positions"
        url = f"{self.ib.BASE_URL}{path}" if hasattr(self.ib, "BASE_URL") else "https://api.ironbeam.com/v1" + path
        async with aiohttp.ClientSession() as sess:
            while True:
                try:
                    # Auth headers – reuse IBClient signing helper via private attr
                    body = ""
                    ts = str(int(time.time() * 1000))
                    base = f"GET|{path}|{ts}|{body}"
                    sig = self._hmac(self.ib._secret, base)  # type: ignore[attr-defined, protected-access]
                    headers = {
                        "IB-API-KEY": os.environ["IRONBEAM_API_KEY"],
                        "IB-API-TIMESTAMP": ts,
                        "IB-API-SIGNATURE": sig,
                    }
                    async with sess.get(url, headers=headers, timeout=5) as resp:
                        if resp.status != 200:
                            raise RuntimeError(f"pos poll HTTP {resp.status}")
                        data = await resp.json()
                        self._update_pos_from_rows(data)
                except Exception as exc:  # pylint: disable=broad-except
                    LOGGER.warning("pos poll error: %s", exc)
                await asyncio.sleep(self.rest_poll_sec)

    def _update_pos_from_rows(self, rows: List[Dict[str, Any]]) -> None:
        for row in rows:
            if str(row.get("symbol", "")).startswith(self.contract):
                self.pos = int(row["qty"])
                break

    # ------------------------------------------------------------------
    # Market-data WebSocket loop
    # ------------------------------------------------------------------

    async def _md_loop(self) -> None:
        while True:
            try:
                async with websockets.connect(self.ws_url, ping_interval=20) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "type": "subscribe",
                                "symbols": [f"{self.contract}_FUT_CME"],
                                "channels": ["ticker"],
                            }
                        )
                    )
                    LOGGER.info("MD subscribed %s", self.contract)
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("type") == "ticker":
                            self.price = float(msg["last"])
                            self._update_buffers(self.price)
                            await self._evaluate_tranches()
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.warning("MD reconnect due to: %s", exc)
                await asyncio.sleep(1)

    # ------------------------------------------------------------------
    # Tranche evaluation dispatcher
    # ------------------------------------------------------------------

    async def _evaluate_tranches(self) -> None:
        if abs(self.pos) > self.position_limit:
            return  # hard guard until exposure reduced
        if self.price is None:
            return
        # iterate active tranches
        for name, tr in self.tranches.items():
            if tr.get("status") != "active":
                continue
            if name == "scalp_add":
                await self._manage_scalp(tr)
            elif name == "core_runner":
                await self._manage_core(tr)

    # ------------------------------------------------------------------
    # Tranche managers
    # ------------------------------------------------------------------

    async def _manage_scalp(self, tr: Dict[str, Any]) -> None:
        qty = int(tr["qty"])
        if abs(self.pos) < qty:
            return  # entry not present yet
        sym = f"{self.contract}_FUT_CME"

        # no need to pre-fetch orders; reconciliation handles it
        want_prices = {
            "tp1": round(tr["oco"]["tp1"] / TICK_SIZE) * TICK_SIZE,
            "tp2": round(tr["oco"]["tp2"] / TICK_SIZE) * TICK_SIZE,
            "stop": round(tr["oco"]["stop"] / TICK_SIZE) * TICK_SIZE,
        }
        await self._reconcile_tranche("scalp_add", want_prices, qty, "BUY")

    async def _manage_core(self, tr: Dict[str, Any]) -> None:
        qty = int(tr["qty"])
        if abs(self.pos) < qty:
            return
        sym = f"{self.contract}_FUT_CME"
        orders = await self._fetch_open_orders(sym)

        # ----- trailing stop (initial only) ---------------------------
        stop_price = round(float(tr["trailing_stop"]["initial"]) / TICK_SIZE) * TICK_SIZE
        if self._core_stop_id is None:
            # initial placement if missing
            if not any(o.get("reduceOnly") and float(o["price"]) == stop_price for o in orders.values()):
                oid = self.ib.submit_order(sym, "BUY", qty, "STOP", price=stop_price, reduce_only=True)
                self._core_stop_id = oid
                self._core_stop_px = stop_price
                LOGGER.info("Core stop placed %.1f", stop_price)
        # ---------- ATR trail logic ----------
        if len(self._bars_1m) >= 15 and self._core_stop_px is not None and self._core_stop_id is not None:
            atr_val = self._atr14(self._bars_1m)
            latest_hi = self._bars_1m[-1]["high"]
            new_stop = latest_hi + atr_val
            new_stop = round(new_stop / TICK_SIZE) * TICK_SIZE
            if new_stop < self._core_stop_px - TICK_SIZE:  # only tighten
                self.ib.modify_order(self._core_stop_id, new_stop)
                LOGGER.info("Core stop trailed to %.1f (ATR %.1f)", new_stop, atr_val)
                self._core_stop_px = new_stop

        # ----- hard targets ------------------------------------------
        want_dict = {"stop": self._core_stop_px}
        for idx, tgt in enumerate(tr.get("hard_targets", []), start=1):
            want_dict[f"tgt{idx}"] = round(float(tgt) / TICK_SIZE) * TICK_SIZE

        await self._reconcile_tranche("core_runner", want_dict, qty, "BUY")

    # ------------------------------------------------------------------
    # REST helpers (async wrappers around sync IBClient or direct REST)
    # ------------------------------------------------------------------

    async def _fetch_open_orders(self, symbol: str) -> Dict[float, Dict[str, Any]]:  # noqa: D401
        """Return mapping price->order for open orders of *symbol*."""
        loop = asyncio.get_running_loop()

        def _do() -> Dict[float, Dict[str, Any]]:
            try:
                raw = self.ib.list_orders(symbol)
                return {float(o["price"]): o for o in raw}
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.warning("list_orders failed: %s", exc)
                return {}

        return await loop.run_in_executor(None, _do)

    async def _cancel_order(self, order_id: str) -> None:  # noqa: D401
        loop = asyncio.get_running_loop()

        def _do_cancel() -> None:
            from requests import delete

            hdr = self._sign("DELETE", f"/orders/{order_id}")
            delete(self.ib.BASE_URL + f"/orders/{order_id}", headers=hdr, timeout=3)

        await loop.run_in_executor(None, _do_cancel)

    # ------------------------------------------------------------------
    # Order reconciliation
    # ------------------------------------------------------------------

    async def _reconcile_tranche(
        self,
        tr_name: str,
        want_prices: Dict[str, float],
        qty: int,
        side: str,
    ) -> None:
        """Ensure all *want_prices* legs exist, cancel rogue reduce-only orders."""
        sym = f"{self.contract}_FUT_CME"
        open_by_px = await self._fetch_open_orders(sym)

        # cancel rogue
        for px, order in list(open_by_px.items()):
            if order.get("reduceOnly") and px not in want_prices.values():
                try:
                    self.ib.cancel_order(order["orderId"])
                    LOGGER.info("%s: cancel rogue %.1f", tr_name, px)
                except Exception as exc:  # pylint: disable=broad-except
                    LOGGER.warning("cancel failed: %s", exc)

        # submit missing
        for leg, px in want_prices.items():
            if px is None:
                continue
            if px not in open_by_px:
                ord_type = "LIMIT" if (side == "BUY" and px < self.price) or (side == "SELL" and px > self.price) else "STOP"
                try:
                    oid = self.ib.submit_order(sym, side, qty, ord_type, price=px, reduce_only=True)
                    self.legs_required[tr_name][leg] = oid
                    if tr_name == "core_runner" and leg == "stop":
                        # refresh cached stop id/px
                        self._core_stop_id = oid
                        self._core_stop_px = px
                    LOGGER.info("%s: add %s %.1f", tr_name, leg, px)
                except Exception as exc:  # pylint: disable=broad-except
                    LOGGER.warning("submit failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sign(self, verb: str, path: str) -> Dict[str, str]:
        """Reuse `ib_order._sign_request` but keep it encapsulated."""
        from live.ib_order import _sign_request  # pylint: disable=import-error

        return _sign_request(self.ib._secret, verb, path)  # type: ignore[attr-defined, protected-access]

    @staticmethod
    def _hmac(secret: str, msg: str) -> str:  # small helper to avoid importing twice
        import hmac
        import hashlib

        return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

    # ------------------------------------------------------------------
    # Tick buffer & 1-min bar construction
    # ------------------------------------------------------------------

    def _update_buffers(self, price: float) -> None:
        """Store tick close and roll 1-minute bars for ATR calc."""
        now = int(time.time())
        self._close_buf.append(price)

        minute = now // 60
        if self._last_bar_min is None:
            self._last_bar_min = minute
            self._bars_1m.append({"high": price, "low": price, "close": price})
            return

        current_bar = self._bars_1m[-1]
        if minute == self._last_bar_min:
            current_bar["high"] = max(current_bar["high"], price)
            current_bar["low"] = min(current_bar["low"], price)
            current_bar["close"] = price
        else:
            # roll new bar(s) if minutes skipped
            for _ in range(minute - self._last_bar_min):  # ensure catch-up
                self._bars_1m.append({"high": price, "low": price, "close": price})
            self._last_bar_min = minute

    # ------------------------------------------------------------------
    # ATR helper
    # ------------------------------------------------------------------

    @staticmethod
    def _atr14(bars: deque[Dict[str, float]]) -> float:
        """Return 14-period ATR for deque of ≥15 1-min bars."""
        if len(bars) < 15:
            return 0.0
        trs: List[float] = []
        prev_close = bars[-15]["close"]
        for b in list(bars)[-14:]:
            tr = max(
                b["high"] - b["low"],
                abs(b["high"] - prev_close),
                abs(b["low"] - prev_close),
            )
            trs.append(tr)
            prev_close = b["close"]
        return statistics.mean(trs)


# ---------------------------------------------------------------------------
# Lightweight manual test when run stand-alone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    adapter = FuturesAdapter()
    adapter.attach()
