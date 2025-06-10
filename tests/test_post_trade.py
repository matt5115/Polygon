import pytest
from client.post_trade import format_trade_for_api

def test_format_trade_for_api():
    raw = {
        "ticker": "AAPL",
        "strategy": "CSP",
        "strike": 180,
        "expiry": "2025-06-20",
        "entry_price": 185.5,
        "premium": 2.5,
        "delta": 0.25,
        "annualized_yield": 0.3,
        "pop": 0.75,
    }
    formatted = format_trade_for_api(raw)
    assert formatted["ticker"] == "AAPL"
    assert formatted["strategy"] == "CSP"
    assert formatted["strike"] == 180.0
    assert formatted["expiry"] == "2025-06-20"
    assert formatted["entry_price"] == 185.5
    assert formatted["premium"] == 2.5
    assert formatted["delta"] == 0.25
    assert formatted["annualized_yield"] == 0.3
    assert formatted["pop"] == 0.75
    assert formatted["rationale"] == ""

def test_format_trade_with_rationale():
    raw = {
        "ticker": "MSFT",
        "strategy": "CC",
        "strike": 420.0,
        "expiry": "2025-07-19",
        "entry_price": 415.0,
        "premium": 8.50,
        "delta": 0.30,
        "annualized_yield": 0.25,
        "pop": 0.70,
        "rationale": "Selling calls against long position"
    }
    formatted = format_trade_for_api(raw)
    assert formatted["ticker"] == "MSFT"
    assert formatted["strategy"] == "CC"
    assert formatted["rationale"] == "Selling calls against long position"

@patch('client.post_trade.requests.post')
def test_post_trade_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_post.return_value = mock_response
    
    trade_data = {
        "ticker": "AAPL",
        "strategy": "CSP",
        "strike": 180.0,
        "expiry": "2025-06-20",
        "premium": 2.50,
        "delta": 0.25,
        "annualized_yield": 0.30,
        "pop": 0.75,
        "rationale": "Test trade"
    }
    
    from client.post_trade import post_trade
    result = post_trade(trade_data)
    assert result is True
    mock_post.assert_called_once()

@patch('client.post_trade.requests.post')
def test_post_trade_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Invalid data"
    mock_post.return_value = mock_response
    
    trade_data = {"ticker": "INVALID"}
    
    from client.post_trade import post_trade
    result = post_trade(trade_data)
    assert result is False
