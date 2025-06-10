import os
import requests
from typing import Dict

API_URL = os.getenv("API_URL", "http://localhost:8000/trades/")

def format_trade_for_api(raw_trade: Dict) -> Dict:
    """Ensure trade fields match backend schema and types."""
    return {
        "ticker": raw_trade["ticker"],
        "strategy": raw_trade["strategy"],  # "CSP" or "CC"
        "strike": float(raw_trade["strike"]),
        "expiry": str(raw_trade["expiry"]),
        "entry_price": float(raw_trade.get("entry_price", 0)),
        "premium": float(raw_trade["premium"]),
        "delta": float(raw_trade["delta"]),
        "annualized_yield": float(raw_trade["annualized_yield"]),
        "pop": float(raw_trade["pop"]),
        "rationale": raw_trade.get("rationale", "")
    }

def post_trade(trade: Dict) -> bool:
    try:
        response = requests.post(API_URL, json=trade)
        if response.status_code == 201:
            print(f"✅ Trade posted: {trade['ticker']} {trade['strike']} {trade['expiry']}")
            return True
        else:
            print(f"❌ Failed to post trade ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"🔥 Exception while posting trade: {e}")
        return False

def post_trade_from_scanner(raw_trade: Dict) -> bool:
    """Format and post a trade from scanner data."""
    formatted = format_trade_for_api(raw_trade)
    return post_trade(formatted)
