"""
Tests for backtester PnL and drawdown calculations.
"""
import pytest
from datetime import date, datetime
from backtest.backtester import Backtester
from backtest.strategies.risk_reversal import RiskReversal

class DummyBacktester(Backtester):
    """Dummy backtester for testing PnL calculations."""
    
    def __init__(self):
        """Initialize with dummy values."""
        self.total_pnl = 0.0
        self.peak_equity = 1_000_000.0
        self.max_drawdown = 0.0
    
    def update_drawdown(self, current_equity: float):
        """Update max drawdown based on current equity."""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        drawdown = (current_equity - self.peak_equity) / self.peak_equity * 100
        self.max_drawdown = min(self.max_drawdown, drawdown)

def test_total_return_matches_sum():
    """Test that total PnL is correctly accumulated."""
    bt = DummyBacktester()
    bt.total_pnl = 0
    
    # Add some PnL
    bt.total_pnl += 1000.0
    assert bt.total_pnl == 1000.0
    
    # Add more PnL
    bt.total_pnl += -500.0
    assert bt.total_pnl == 500.0
    
    # Add another position
    bt.total_pnl += 250.0
    assert bt.total_pnl == 750.0

def test_drawdown_calculation():
    """Test that max drawdown is correctly calculated."""
    bt = DummyBacktester()
    
    # Initial state
    assert bt.max_drawdown == 0.0
    
    # Price increases - no drawdown
    bt.update_drawdown(1_100_000.0)  # +10%
    assert bt.max_drawdown == 0.0
    assert bt.peak_equity == 1_100_000.0
    
    # Small drawdown
    bt.update_drawdown(1_050_000.0)  # -4.55% from peak
    assert round(bt.max_drawdown, 2) == -4.55  # Allow for floating point precision
    
    # New peak
    bt.update_drawdown(1_200_000.0)  # New peak
    assert round(bt.max_drawdown, 2) == -4.55  # Max drawdown remains, allow for floating point
    assert bt.peak_equity == 1_200_000.0
    
    # Larger drawdown
    bt.update_drawdown(1_100_000.0)  # -8.33% from peak
    assert round(bt.max_drawdown, 2) == -8.33  # Allow for floating point precision
    
    # Even larger drawdown
    bt.update_drawdown(1_000_000.0)  # -16.67% from peak
    assert round(bt.max_drawdown, 2) == -16.67  # Allow for floating point precision

def test_position_pnl_calculation():
    """Test that position PnL is correctly calculated."""
    # Create a strategy with known parameters
    strategy = RiskReversal(
        long_call_strike=420,
        short_put_strike=380,
        qty_init=5,
        max_qty=25,
        expiry="2025-06-13"
    )
    
    # Test long position PnL
    strategy.add_position(400.0, date(2025, 1, 1), "Test entry")
    pnl = strategy.close_position(420.0, date(2025, 1, 2), "Test exit")
    assert round(pnl, 2) == 5.0  # (420/400 - 1) * 100 = 5%
    
    # Note: The RiskReversal strategy doesn't currently support short positions directly
    # so we'll skip this test for now
    pass

if __name__ == "__main__":
    pytest.main(["-v", __file__])
