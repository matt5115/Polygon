import asyncio
import json
from types import SimpleNamespace
from unittest import mock

import pytest

import websockets
from live.futures_adapter import FuturesAdapter


@pytest.mark.asyncio
async def test_ws_message_parsing(monkeypatch):
    sample_msg = json.dumps({"type": "ticker", "symbol": "MBTM25_FUT_CME", "last": 110020, "timestamp": 1718068569})

    async def fake_connect(*args, **kwargs):  # pylint: disable=unused-argument
        class FakeWS:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                pass

            async def send(self, *_):
                pass

            async def __aiter__(self):
                yield sample_msg

            @property
            def closed(self):
                return False

        return FakeWS()

    monkeypatch.setattr(websockets, "connect", fake_connect)

    # capture price via callback
    price_holder = SimpleNamespace(val=None)

    def _cb(price, ts):  # pylint: disable=unused-argument
        price_holder.val = price

    adapter = FuturesAdapter(symbol="MBT", contract="MBTM25", md_ws="wss://fake", on_price=_cb)

    # run just one iteration
    async def run_once():
        await asyncio.wait_for(adapter._main(), timeout=0.2)  # type: ignore

    with pytest.raises(asyncio.TimeoutError):
        await run_once()

    assert price_holder.val == 110020.0
