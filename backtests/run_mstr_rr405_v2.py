"""
Backtest runner for MSTR May-Jun 2025 Risk Reversal strategy (v2).

Strategy Parameters:
- Initial contracts: 5 (≈ $28.5K Reg-T margin ≈ 2% of $1.4M)
- Max position: 25 contracts (≈ $140K margin ≈ 10% of cash)
- Scale-in: Add +5 contracts each time MSTR closes +$15 above the last add-level
- Profit-take: Close tranche if net debit ≥ +150% or MSTR ≥ $440
- Stop-loss: Close if MSTR ≤ $389 (updated from $385)
- Time exit: Force-close at expiry (13 Jun 2025)
"""
import os
import sys
from datetime import datetime, date

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.backtester import Backtester
from backtest.strategies.risk_reversal import RiskReversal

def main():
    # Initialize the strategy with updated parameters
    strategy = RiskReversal(
        long_call_strike=420,
        short_put_strike=380,
        qty_init=5,
        qty_step=5,
        add_trigger=15,
        take_profit_pct=1.5,
        stop_lvl=389,  # Updated from 385
        iv_stop=0.10,
        max_qty=25,
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
    os.makedirs("backtests/mstr_rr405_v2", exist_ok=True)
    
    # Generate markdown report
    bt.to_markdown("backtests/mstr_rr405_v2/report.md")
    print("Backtest complete. Report saved to backtests/mstr_rr405_v2/report.md")

if __name__ == "__main__":
    main()
