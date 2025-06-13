#!/usr/bin/env python3
"""Thin synchronous wrapper around Ironbeam v1 REST API.

Exposes minimal helpers needed by the Futures adapter to place/modify/cancel
orders for the CME Micro-Bitcoin Futures contract (MBT).
"""
from __future__ import annotations

import json
import os
import time
import hmac
import hashlib
from typing import Tuple, Dict, Any

import requests

# ---------------------------------------------------------------------------
# Required environment – fail fast if missing
# ---------------------------------------------------------------------------
_missing = [v for v in ("IRONBEAM_API_KEY", "IRONBEAM_API_SECRET", "IRONBEAM_ACCOUNT") if v not in os.environ]
if _missing:
    raise RuntimeError(f"Missing env vars: {', '.join(_missing)}")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL: str = "https://api.ironbeam.com/v1"
TIMEOUT: int = 3          # seconds
RETRY_MAX: int = 3
TICK_SIZE: float = 0.5    # USD per price tick (MBT minimal increment)
HEADERS_CT: Dict[str, str] = {"Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# Signing helper
# ---------------------------------------------------------------------------

def _sign_request(secret: str, verb: str, path: str, body: str = "") -> Dict[str, str]:
    """Return Ironbeam auth headers for *verb* request."""
    ts = str(int(time.time() * 1000))
    base = f"{verb.upper()}|{path}|{ts}|{body}"
    sig = hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()
    return {
        "IB-API-KEY": os.environ["IRONBEAM_API_KEY"],
        "IB-API-TIMESTAMP": ts,
        "IB-API-SIGNATURE": sig,
        **HEADERS_CT,
    }


# ---------------------------------------------------------------------------
# Client wrapper
# ---------------------------------------------------------------------------

class IBClient:
    """Synchronous minimal Ironbeam REST client."""

    def __init__(self) -> None:
        self._secret: str = os.environ["IRONBEAM_API_SECRET"]
        self.account: str = os.environ["IRONBEAM_ACCOUNT"]
        self.BASE_URL: str = BASE_URL

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":"))
        headers = _sign_request(self._secret, "POST", path, body)
        for attempt in range(1, RETRY_MAX + 1):
            resp = requests.post(BASE_URL + path, headers=headers, data=body, timeout=TIMEOUT)
            if resp.status_code < 500:
                break
            time.sleep(0.5 * attempt)  # simple linear back-off
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        ord_type: str,
        price: float | None = None,
        tif: str = "GTC",
        reduce_only: bool = False,
    ) -> str:
        """Submit an order and return Ironbeam `orderId`.

        If *price* provided, rounds it to nearest tick.
        """
        if price is not None:
            price = round(price / TICK_SIZE) * TICK_SIZE

        payload = {
            "account": self.account,
            "symbol": symbol,
            "side": side,
            "orderType": ord_type,
            "quantity": qty,
            "timeInForce": tif,
            "price": price,
            "reduceOnly": reduce_only,
        }
        res = self._post("/orders", payload)
        return res["orderId"]

    # Convenience helpers -------------------------------------------------

    def submit_bracket(self, symbol: str, qty: int, tp: float, sl: float) -> Tuple[str, str]:
        """Place TP + SL reduce-only child orders; return their IDs."""
        oid_tp = self.submit_order(symbol, "BUY", qty, "LIMIT", price=tp, reduce_only=True)
        oid_sl = self.submit_order(symbol, "BUY", qty, "STOP", price=sl, reduce_only=True)
        return oid_tp, oid_sl

    def modify_order(self, order_id: str, price: float) -> None:
        """Modify existing order's price (typically trailing stop)."""
        from requests import put  # local import to keep top clean

        price = round(price / TICK_SIZE) * TICK_SIZE
        path = f"/orders/{order_id}"
        body = json.dumps({"price": price})
        headers = _sign_request(self._secret, "PUT", path, body)
        resp = put(self.BASE_URL + path, headers=headers, data=body, timeout=TIMEOUT)
        resp.raise_for_status()

    # ----------------------- order maintenance -----------------------

    def list_orders(self, symbol: str) -> list[dict]:
        """Return list of *open* orders for given symbol."""
        from requests import get

        path = f"/orders?symbol={symbol}&status=open"
        headers = _sign_request(self._secret, "GET", path)
        resp = get(self.BASE_URL + path, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def cancel_order(self, order_id: str) -> None:
        """Cancel an existing order."""
        from requests import delete

        path = f"/orders/{order_id}"
        headers = _sign_request(self._secret, "DELETE", path)
        resp = delete(self.BASE_URL + path, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
