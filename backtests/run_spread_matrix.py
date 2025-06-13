"""
Run backtest for multiple debit spread strategies with different strike widths.
"""
import sys
import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from backtest.backtester import Backtester
from strategies.debit_spread import DebitSpread

def run_backtest(underlying, start_date, end_date, short_strike_pct, long_strike_pct, width, qty):
    """Run a single backtest with given parameters."""
    strategy = DebitSpread(
        qty_init=qty,
        qty_step=qty,
        max_qty=qty * 5,
        dte=30,
        short_strike_pct=short_strike_pct,
        long_strike_pct=long_strike_pct,
        stop_loss_pct=0.80,
        take_profit_pct=0.50,
        close_at_expiry=True
    )
    
    backtester = Backtester(
        underlying=underlying,
        start=start_date,
        end=end_date,
        strategy=strategy,
        initial_capacity=100000,
        fee_per_contract=0.50,
        slippage_pct=0.001
    )
    
    backtester.run()
    
    # Return summary metrics
    return {
        'strategy': f'spread_{int(short_strike_pct*1000)}_{int(long_strike_pct*1000)}',
        'width': width,
        'total_return': backtester.total_pnl / backtester.initial_capacity * 100,
        'max_drawdown': backtester.max_drawdown * 100,
        'sharpe': backtester.calculate_sharpe_ratio(),
        'win_rate': backtester.calculate_win_rate()
    }

def main():
    underlying = "MSTR"
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Define spread strategies to test
    spreads = [
        (0.95, 1.00, '5%'),    # 395/420
        (0.95, 1.05, '10%'),   # 395/425
        (0.95, 1.10, '15%'),   # 395/435
    ]
    
    results = []
    for short_pct, long_pct, width in spreads:
        try:
            result = run_backtest(underlying, start_date, end_date, 
                               short_pct, long_pct, width, qty=5)
            results.append(result)
            print(f"Completed {result['strategy']}: {result['total_return']:.1f}%")
        except Exception as e:
            print(f"Error running {short_pct}-{long_pct}: {str(e)}")
    
    # Save results
    os.makedirs("backtests/results", exist_ok=True)
    df = pd.DataFrame(results)
    output_file = f"backtests/results/{underlying}_spread_matrix_{end_date}.csv"
    df.to_csv(output_file, index=False)
    print(f"\nResults saved to {output_file}")

if __name__ == "__main__":
    main()
