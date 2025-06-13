import os
import json
import importlib
import types

# Ensure env vars present before importing the module under test
os.environ["IRONBEAM_API_KEY"] = "k"
os.environ["IRONBEAM_API_SECRET"] = "s"
os.environ["IRONBEAM_ACCOUNT"] = "A1"

ib_order = importlib.import_module("live.ib_order")
IBClient = ib_order.IBClient
_sign_request = ib_order._sign_request


def test_sign_request():
    hdr = _sign_request("sec", "POST", "/path", "{}")
    assert "IB-API-KEY" in hdr and "IB-API-SIGNATURE" in hdr


def test_submit_order_round(monkeypatch):
    captured: dict[str, dict] = {}

    def fake_post(url, headers, data, timeout):  # noqa: D401,E501 pylint: disable=unused-argument
        captured["body"] = json.loads(data)

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"orderId": "123"}

        return R()

    monkeypatch.setattr(ib_order.requests, "post", fake_post)

    client = IBClient()
    client.submit_order("MBTM25_FUT_CME", "SELL", 1, "LIMIT", price=110027.3)
    assert captured["body"]["price"] == 110027.5  # rounded tick
