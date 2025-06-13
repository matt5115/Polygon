"""
Backtest runner for MSTR May-Jun 2025 Call Debit Spread strategy.

Strategy Parameters:
- Long Call Strike: $400
- Short Call Strike: $430
- Quantity: 10 spreads
- Expiry: 13 Jun 2025
"""
import os
import sys
from datetime import datetime, date

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.backtester import Backtester
from backtest.strategies.call_debit_spread import CallDebitSpread

def main():
    # Initialize the strategy
    strategy = CallDebitSpread(
        long_strike=400,
        short_strike=430,
        qty=10,  # Approximately same buying power as 5-lot risk reversal
        expiry="2025-06-13"
    )
    
    # Initialize and run the backtest
    bt = Backtester(
        underlying="MSTR",
        start="2025-05-12",
        end="2025-06-13",  # Full expiry
        strategy=strategy,
        initial_capital=1_400_000  # $1.4M initial capital
    )
    
    # Run the backtest and generate report
    bt.run()
    
    # Ensure output directory exists
    os.makedirs("backtests/mstr_debit400_430", exist_ok=True)
    
    # Generate markdown report
    bt.to_markdown("backtests/mstr_debit400_430/report.md")
    print("Backtest complete. Report saved to backtests/mstr_debit400_430/report.md")

if __name__ == "__main__":
    main()
