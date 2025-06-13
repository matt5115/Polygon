import asyncio
from collections import deque
import pytest

from live.futures_adapter import FuturesAdapter


@pytest.mark.asyncio
async def test_atr_trails(monkeypatch):
    fa = FuturesAdapter()
    # Pretend core tranche filled
    fa.pos = fa.tranches["core_runner"]["qty"]
    fa._core_stop_id = "STOP1"
    fa._core_stop_px = 105_200.0

    # fabricate 15 bars; last bar high lowers such that new stop < current
    bars = []
    for _ in range(14):
        bars.append({"high": 105_000.0, "low": 104_500.0, "close": 104_700.0})
    bars.append({"high": 104_600.0, "low": 104_100.0, "close": 104_300.0})
    fa._bars_1m = deque(bars, maxlen=15)

    modified = {}
    monkeypatch.setattr(fa.ib, "modify_order", lambda oid, price: modified.update({"price": price}))

    await fa._manage_core(fa.tranches["core_runner"])

    assert modified, "modify_order should have been called"
    assert modified["price"] < 105_200.0
