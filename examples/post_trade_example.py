from client.post_trade import post_trade_from_scanner

trade_data = {
    "ticker": "AAPL",
    "strategy": "CSP",
    "strike": 180.0,
    "expiry": "2025-06-20",
    "entry_price": 185.5,
    "premium": 2.50,
    "delta": 0.25,
    "annualized_yield": 0.30,
    "pop": 0.75,
    "rationale": "High probability trade with good risk/reward"
}

post_trade_from_scanner(trade_data)
