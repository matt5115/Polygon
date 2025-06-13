"""Tests for polygon_helpers module."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from utils.polygon_helpers import (
    list_contracts,
    fetch_iv_snapshot,
    get_stock_price,
    find_atm_contracts
)

# Sample test data
SAMPLE_CONTRACTS = [
    {"ticker": "O:MSTR250613C00405000", "contract_type": "call", "strike_price": 405.0, "expiration_date": "2025-06-13"},
    {"ticker": "O:MSTR250613P00405000", "contract_type": "put", "strike_price": 405.0, "expiration_date": "2025-06-13"},
    {"ticker": "O:MSTR250613C00410000", "contract_type": "call", "strike_price": 410.0, "expiration_date": "2025-06-13"},
    {"ticker": "O:MSTR250613P00400000", "contract_type": "put", "strike_price": 400.0, "expiration_date": "2025-06-13"},
]

SAMPLE_SNAPSHOT = MagicMock()
SAMPLE_SNAPSHOT.implied_volatility = 0.1  # 10% IV


def test_find_atm_contracts():
    """Test finding ATM call and put contracts."""
    # With stock price of 404.90, the 405 strike is ATM
    call_ticker, put_ticker = find_atm_contracts(SAMPLE_CONTRACTS, 404.90)
    assert call_ticker == "O:MSTR250613C00405000"
    assert put_ticker == "O:MSTR250613P00405000"
    
    # Test with no contracts
    call_ticker, put_ticker = find_atm_contracts([], 404.90)
    assert call_ticker is None
    assert put_ticker is None


def test_find_atm_contracts_no_matches():
    """Test with no matching contracts."""
    # Only calls, no puts
    calls = [c for c in SAMPLE_CONTRACTS if c["contract_type"] == "call"]
    call_ticker, put_ticker = find_atm_contracts(calls, 404.90)
    assert call_ticker == "O:MSTR250613C00405000"
    assert put_ticker is None


@patch('utils.polygon_helpers.requests.get')
def test_get_stock_price(mock_get):
    """Test fetching stock price."""
    # Mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {"close": 404.90}
    mock_get.return_value = mock_response
    
    price = get_stock_price("MSTR", "2025-05-12", "test_key")
    assert price == 404.90


@patch('utils.polygon_helpers.RESTClient')
def test_list_contracts(mock_client):
    """Test listing option contracts."""
    # Mock client response
    mock_instance = mock_client.return_value
    mock_instance.get_reference_options_contracts.return_value = MagicMock(
        results=SAMPLE_CONTRACTS
    )
    
    contracts = list_contracts("MSTR", "2025-06-13", mock_instance)
    assert len(contracts) == 4
    assert contracts[0]["ticker"] == "O:MSTR250613C00405000"


@patch('utils.polygon_helpers.RESTClient')
def test_fetch_iv_snapshot(mock_client):
    """Test fetching IV snapshot."""
    # Mock client response
    mock_instance = mock_client.return_value
    mock_instance.get_snapshot_option_contract.return_value = SAMPLE_SNAPSHOT
    
    snapshot = fetch_iv_snapshot("O:MSTR250613C00405000", "2025-05-12", mock_instance)
    assert snapshot.implied_volatility == 0.1
