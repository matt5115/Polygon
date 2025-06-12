"""
Test the backtester with transaction costs and slippage.
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path to import backtester
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backtest.backtester import Backtester, Strategy

class TestStrategy(Strategy):
    """Simple test strategy that enters and exits on specific dates."""
    
    def __init__(self):
        self.entry_date = date(2023, 1, 10)
        self.exit_date = date(2023, 1, 20)
        self.positions = []
        self.trades = []
        self.qty_init = 10  # 10 contracts = 1000 shares
        self.qty_step = 5   # 5 contracts per add
        self.max_qty = 20   # Max 20 contracts
        self.last_add_price = None
    
    def should_enter(self, price: float, trade_date: date) -> tuple[bool, str]:
        if trade_date == self.entry_date:
            return True, "Test entry"
        return False, ""
    
    def should_add(self, price: float, trade_date: date) -> tuple[bool, str]:
        """Don't add to position in this test."""
        return False, ""
    
    def should_exit(self, price: float, trade_date: date, iv: Optional[float] = None, 
                  current_pnl: Optional[float] = None) -> tuple[bool, str]:
        if trade_date == self.exit_date:
            return True, "Test exit"
        return False, ""
    
    def add_position(self, price: float, trade_date: date, reason: str = ""):
        self.positions.append((price, trade_date, reason))
        self.last_add_price = price
    
    def close_position(self, price: float, trade_date: date, reason: str = "") -> float:
        if not self.positions:
            return 0.0
            
        # Calculate PnL for the position
        entry_price = self.positions[0][0]  # Use first entry price for simplicity
        pnl_pct = (price / entry_price - 1) * 100
        
        # Record the trade
        self.trades.append({
            'date': trade_date,
            'action': 'SELL',
            'price': price,
            'qty': self.qty_init,
            'reason': reason,
            'pnl_pct': pnl_pct,
            'commission': 0.50,  # $0.50 per contract
            'slippage': price * 0.001  # 0.1% slippage
        })
        
        # Clear positions
        self.positions = []
        self.last_add_price = None
        return pnl_pct

@pytest.fixture
def mock_historical_data():
    """Create a mock historical data DataFrame."""
    dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='B')
    prices = np.linspace(100, 110, len(dates))  # Linearly increasing prices
    ivs = np.full(len(dates), 0.2)  # Constant 20% IV
    
    return pd.DataFrame({
        'close': prices,
        'iv': ivs
    }, index=dates)

def test_backtester_with_costs(mock_historical_data, tmp_path):
    """Test the backtester with transaction costs and slippage."""
    # Setup test strategy
    strategy = TestStrategy()
    
    # Initialize backtester with fees and slippage
    backtester = Backtester(
        underlying="SPY",
        start="2023-01-01",
        end="2023-01-31",
        strategy=strategy,
        initial_capital=100000,  # $100k initial capital
        fee_per_contract=0.50,   # $0.50 per contract
        slippage_pct=0.001       # 0.1% slippage
    )
    
    # Mock the fetch_historical_data method to return our test data
    backtester.fetch_historical_data = MagicMock(return_value=mock_historical_data)
    
    # Run the backtest
    backtester.run()
    
    # Generate the report
    report_path = tmp_path / "backtest_report.md"
    backtester.to_markdown(str(report_path))
    
    # Verify the report was created
    assert os.path.exists(report_path)
    
    # Read the report
    with open(report_path, 'r') as f:
        report = f.read()
    
    # Basic assertions about the report content
    assert "Backtest Report" in report
    assert "Performance Summary" in report
    assert "Total Commissions" in report
    assert "Total Slippage" in report
    
    # Verify trade was executed
    assert len(strategy.trades) > 0
    
    # Verify costs were applied
    assert backtester.total_commissions > 0
    assert backtester.total_slippage > 0
    
    print("\nBacktest report generated successfully:")
    print(f"- Trades executed: {len(strategy.trades)}")
    print(f"- Total commissions: ${backtester.total_commissions:.2f}")
    print(f"- Total slippage: ${backtester.total_slippage:.2f}")

if __name__ == "__main__":
    # Run the test directly to see the output
    test_data = mock_historical_data()
    test_backtester_with_costs(test_data, "/tmp")
