import pytest

from live.futures_adapter import FuturesAdapter


@pytest.mark.asyncio
async def test_reconcile_cancels_and_adds(monkeypatch):
    fa = FuturesAdapter()
    fa.price = 103_500.0

    # Mock open orders with one rogue reduce-only order
    rogue = {"orderId": "X", "price": 104_000.0, "reduceOnly": True, "quantity": 10}
    monkeypatch.setattr(fa, "_fetch_open_orders", lambda *_: {104_000.0: rogue})

    canceled, added = [], []
    monkeypatch.setattr(fa.ib, "cancel_order", lambda oid: canceled.append(oid))
    monkeypatch.setattr(fa.ib, "submit_order", lambda *a, **k: added.append(k["price"]) or "NEW")

    want = {"tp1": 103_300.0, "tp2": 102_950.0, "stop": 104_400.0}
    await fa._reconcile_tranche("scalp_add", want, qty=10, side="BUY")

    assert "X" in canceled
    assert 103_300.0 in added and 102_950.0 in added
