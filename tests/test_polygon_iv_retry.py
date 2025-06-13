"""
Tests for Polygon IV fetch functionality with retry logic.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import time

from utils.polygon_helpers import fetch_iv_snapshot

class MockPolygonClient:
    """Mock Polygon REST client for testing."""
    
    def __init__(self, responses=None):
        """Initialize with a list of responses to return."""
        self.responses = responses or []
        self.calls = 0
    
    def get_snapshot_option_contract(self, **kwargs):
        """Mock method to return the next response or raise an exception."""
        if self.calls >= len(self.responses):
            raise ValueError("No more mock responses configured")
            
        response = self.responses[self.calls]
        self.calls += 1
        
        if isinstance(response, Exception):
            raise response
            
        return response

def test_fetch_iv_success():
    """Test successful IV fetch on first attempt."""
    # Setup mock client with a successful response
    mock_client = MockPolygonClient([
        MagicMock(implied_volatility=0.35, delta=0.5, gamma=0.1)
    ])
    
    # Call the function
    result = fetch_iv_snapshot(
        contract_ticker="O:MSTR250612C00405000",
        as_of="2025-06-11",
        client=mock_client
    )
    
    # Verify results
    assert result['implied_volatility'] == 0.35
    assert result['delta'] == 0.5
    assert result['gamma'] == 0.1
    assert mock_client.calls == 1

def test_fetch_iv_retry_success():
    """Test IV fetch with one failure then success."""
    # Setup mock client with one failure then success
    mock_client = MockPolygonClient([
        ValueError("Temporary error"),
        MagicMock(implied_volatility=0.40)
    ])
    
    # Call the function with retries
    result = fetch_iv_snapshot(
        contract_ticker="O:MSTR250612C00405000",
        as_of="2025-06-11",
        client=mock_client,
        max_retries=3,
        retry_delay=0.1
    )
    
    # Verify results
    assert result['implied_volatility'] == 0.40
    assert mock_client.calls == 2

def test_fetch_iv_missing_data():
    """Test IV fetch when IV data is missing."""
    # Setup mock client with missing IV data
    mock_client = MockPolygonClient([
        MagicMock(implied_volatility=None),  # First attempt: missing IV
        MagicMock(spec=[])  # Second attempt: no IV attribute at all
    ])
    
    # Should raise ValueError after retries
    with pytest.raises(ValueError, match="IV missing for"):
        fetch_iv_snapshot(
            contract_ticker="O:MSTR250612C00405000",
            as_of="2025-06-11",
            client=mock_client,
            max_retries=1
        )
    
    assert mock_client.calls == 2  # Initial + 1 retry

def test_fetch_iv_exponential_backoff():
    """Test that retries use exponential backoff."""
    # Setup mock client that always fails
    mock_client = MockPolygonClient([
        Exception("Error 1"),
        Exception("Error 2"),
        Exception("Error 3")
    ])
    
    # Patch time.sleep to track delays
    with patch('time.sleep') as mock_sleep:
        # Should raise after all retries
        with pytest.raises(Exception, match="Failed to fetch IV"):
            fetch_iv_snapshot(
                contract_ticker="O:MSTR250612C00405000",
                as_of="2025-06-11",
                client=mock_client,
                max_retries=2,
                retry_delay=0.1
            )
        
        # Verify sleep was called with increasing delays
        assert mock_sleep.call_count == 2
        # First delay: 0.1 * (0 + 1) = 0.1
        assert 0.09 < mock_sleep.call_args_list[0][0][0] < 0.11
        # Second delay: 0.1 * (1 + 1) = 0.2
        assert 0.19 < mock_sleep.call_args_list[1][0][0] < 0.21

if __name__ == "__main__":
    pytest.main(["-v", __file__])
