import asyncio
import types
import pytest

from live.futures_adapter import FuturesAdapter


@pytest.mark.asyncio
async def test_sends_bracket(monkeypatch):
    # Use real config but adapter logic is patched to avoid network.
    fa = FuturesAdapter()
    fa.pos = 10  # emulate filled scalp tranche
    fa.price = 103_350  # current price

    sent = []
    monkeypatch.setattr(fa.ib, "submit_order", lambda *a, **kw: sent.append((a, kw)))
    monkeypatch.setattr(fa, "_fetch_open_orders", lambda *_: [])

    await fa._manage_scalp(fa.tranches["scalp_add"])  # type: ignore[arg-type]
    # Expect at least one LIMIT or STOP order submission
    kinds = [args[0][3] for args, _ in sent]  # ord_type is 4th positional arg
    assert any(k in ("LIMIT", "STOP") for k in kinds)
