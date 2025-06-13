"""
Run backtest for MSTR Risk Reversal 40-50 strategy (v3) with transaction costs.
"""
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from backtest.backtester import Backtester
from strategies.risk_reversal import RiskReversal
from datetime import datetime, timedelta

def main():
    # Strategy parameters
    underlying = "MSTR"
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Initialize strategy
    strategy = RiskReversal(
        qty_init=5,
        qty_step=5,
        max_qty=25,
        dte=30,
        put_strike_pct=0.95,  # 5% OTM
        call_strike_pct=1.05,  # 5% OTM
        stop_loss_pct=0.95,    # 5% stop
        take_profit_pct=1.20,  # 20% target
        add_trigger=0.15,      # 15% move to add
        close_at_expiry=True
    )
    
    # Initialize backtester with transaction costs
    backtester = Backtester(
        underlying=underlying,
        start=start_date,
        end=end_date,
        strategy=strategy,
        initial_capital=100000,  # $100k initial capital
        fee_per_contract=0.50,   # $0.50 per contract
        slippage_pct=0.001       # 0.1% slippage
    )
    
    # Run backtest
    backtester.run()
    
    # Generate and save report
    os.makedirs("backtests/results", exist_ok=True)
    report_path = f"backtests/results/{underlying}_RR405_v3_{end_date}.md"
    backtester.to_markdown(report_path)
    print(f"Report saved to {report_path}")

if __name__ == "__main__":
    main()
