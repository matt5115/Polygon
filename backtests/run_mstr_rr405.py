"""
Backtest runner for MSTR May-Jun 2025 Risk Reversal strategy.

Strategy Parameters:
- Initial contracts: 5 (≈ $28.5K Reg-T margin ≈ 2% of $1.4M)
- Max position: 25 contracts (≈ $140K margin ≈ 10% of cash)
- Scale-in: Add +5 contracts when MSTR closes +$15 above last add-level
- Profit-take: Close tranche if net debit ≥ +150% or MSTR ≥ $440
- Risk-off: Close if MSTR ≤ $385 and ATM IV ≤ 10%
- Time exit: Force-close 5 trading days before expiry (≈ 8 Jun 2025)
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from polygon import RESTClient
import os
from dotenv import load_dotenv
from utils.polygon_helpers import list_contracts, fetch_iv_snapshot, get_stock_price, find_atm_contracts

# Load environment variables
load_dotenv()
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
if not POLYGON_API_KEY:
    raise ValueError("POLYGON_API_KEY environment variable not set")

class RiskReversal:
    """Risk Reversal options strategy backtester."""
    
    def __init__(
        self,
        long_call_strike: float,
        short_put_strike: float,
        qty_init: int = 5,
        qty_step: int = 5,
        add_trigger: float = 15.0,
        take_profit_pct: float = 1.5,
        stop_lvl: float = 385.0,
        iv_stop: float = 0.10,
        max_qty: int = 25,
        expiry: str = "2025-06-13"  # Expiry date in YYYY-MM-DD
    ):
        """Initialize the risk reversal strategy.
        
        Args:
            long_call_strike: Strike price for long calls
            short_put_strike: Strike price for short puts
            qty_init: Initial number of contracts
            qty_step: Number of contracts to add on scale-in
            add_trigger: Price movement required to add more contracts ($)
            take_profit_pct: Take profit level as a multiple of initial debit
            stop_lvl: Price level for stop loss
            iv_stop: IV level for risk-off exit
            max_qty: Maximum number of contracts to hold
            expiry: Option expiration date (YYYY-MM-DD)
        """
        self.long_call_strike = long_call_strike
        self.short_put_strike = short_put_strike
        self.qty_init = qty_init
        self.qty_step = qty_step
        self.add_trigger = add_trigger
        self.take_profit_pct = take_profit_pct
        self.stop_lvl = stop_lvl
        self.iv_stop = iv_stop
        self.max_qty = max_qty
        self.expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
        
        # State variables
        self.positions = []  # List of (entry_price, quantity, entry_date)
        self.last_add_price = None
        self.trades = []  # Track all trades for reporting
    
    def should_enter(self, price: float, date: datetime.date) -> Tuple[bool, str]:
        """Check if we should enter a new position."""
        if not self.positions and price > self.short_put_strike:
            return True, "Initial entry"
        return False, ""
    
    def should_add(self, price: float, date: datetime.date) -> Tuple[bool, str]:
        """Check if we should add to the position."""
        if not self.positions:
            return False, "No existing position"
            
        current_qty = sum(qty for _, qty, _ in self.positions)
        if current_qty >= self.max_qty:
            return False, "Max position size reached"
            
        if price >= self.last_add_price + self.add_trigger:
            self.last_add_price = price
            return True, f"Price moved +{self.add_trigger} above last add level"
            
        return False, ""
    
    def should_exit(
        self, 
        price: float, 
        date: datetime.date, 
        iv: Optional[float] = None,
        current_pnl: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Check if we should exit the position."""
        if not self.positions:
            return False, "No position to exit"
            
        # Time-based exit (5 trading days before expiry)
        days_to_expiry = (self.expiry - date).days
        if days_to_expiry <= 5:
            return True, f"Approaching expiry ({days_to_expiry} days left)"
            
        # Stop loss
        if price <= self.stop_lvl:
            if iv is not None and iv <= self.iv_stop:
                return True, f"Stop loss triggered at {price} with IV {iv*100:.1f}%"
        
        # Take profit
        if current_pnl is not None and current_pnl >= self.take_profit_pct:
            return True, f"Take profit reached: {current_pnl:.1f}x"
            
        # Price target
        if price >= 440:  # Hard-coded from strategy
            return True, f"Price target reached: {price}"
            
        return False, ""
    
    def add_position(self, price: float, date: datetime.date, reason: str = ""):
        """Add a new position."""
        current_qty = sum(qty for _, qty, _ in self.positions)
        qty = min(self.qty_step, self.max_qty - current_qty)
        if qty > 0:
            self.positions.append((price, qty, date))
            self.last_add_price = price  # Update last_add_price when adding a position
            self.trades.append({
                'date': date,
                'action': 'BUY',
                'price': price,
                'qty': qty,
                'reason': reason or "Initial entry"
            })
    
    def close_position(self, price: float, date: datetime.date, reason: str = ""):
        """Close all positions."""
        if not self.positions:
            return 0
            
        total_qty = sum(qty for _, qty, _ in self.positions)
        avg_entry = sum(p * q for p, q, _ in self.positions) / total_qty
        pnl = (price / avg_entry - 1) * 100  # PnL in %
        
        self.trades.append({
            'date': date,
            'action': 'SELL',
            'price': price,
            'qty': total_qty,
            'reason': reason,
            'pnl_pct': pnl
        })
        
        self.positions = []
        self.last_add_price = None
        return pnl


class Backtester:
    """Backtesting engine for options strategies."""
    
    def __init__(
        self,
        underlying: str,
        start: str,
        end: str,
        strategy: RiskReversal,
        initial_capital: float = 1_400_000  # $1.4M initial capital
    ):
        """Initialize the backtester."""
        self.underlying = underlying.upper()
        self.start_date = datetime.strptime(start, "%Y-%m-%d").date()
        self.end_date = datetime.strptime(end, "%Y-%m-%d").date()
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.client = RESTClient(api_key=POLYGON_API_KEY)
        
        # Results
        self.equity_curve = []
        self.trades = []
    
    def fetch_historical_data(self) -> pd.DataFrame:
        """Fetch historical price and IV data from Polygon."""
        # Get daily bars for the underlying
        aggs = []
        for a in self.client.list_aggs(
            ticker=self.underlying,
            multiplier=1,
            timespan="day",
            from_=self.start_date.strftime("%Y-%m-%d"),
            to=self.end_date.strftime("%Y-%m-%d"),
            limit=50000
        ):
            aggs.append(a)
        
        if not aggs:
            raise ValueError(f"No data found for {self.underlying} from {self.start_date} to {self.end_date}")
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'date': pd.Timestamp(a.timestamp, unit='ms').date(),
            'open': a.open,
            'high': a.high,
            'low': a.low,
            'close': a.close,
            'volume': a.volume,
            'vwap': a.vwap
        } for a in aggs])
        
        # Get IV data (simplified - in reality, you'd need to fetch option chain data)
        df['iv'] = 0.0  # Placeholder - would need to fetch actual IV data
        
        return df.set_index('date').sort_index()
    
    def run(self):
        """Run the backtest."""
        print(f"Starting backtest for {self.underlying} from {self.start_date} to {self.end_date}")
        
        # Get historical data
        try:
            data = self.fetch_historical_data()
            print(f"Fetched {len(data)} days of data")
        except Exception as e:
            print(f"Error fetching data: {e}")
            return
        
        # Initialize variables
        current_capital = self.initial_capital
        position = None
        
        for idx, row in data.iterrows():
            date = idx.date() if hasattr(idx, 'date') else idx
            price = row['close']
            iv = row.get('iv', 0.0)  # Default to 0 if IV not available
            
            # Print progress
            print(f"\rProcessing {date}: ${price:.2f}", end="")
            
            # Check for entry
            if not position:
                should_enter, reason = self.strategy.should_enter(price, date)
                if should_enter:
                    self.strategy.add_position(price, date, reason)
                    position = {
                        'entry_price': price,
                        'entry_date': date,
                        'qty': self.strategy.qty_init
                    }
                    print(f"\n  ENTRY: {reason} at ${price:.2f}")
            else:
                # Check for adds
                should_add, reason = self.strategy.should_add(price, date)
                if should_add:
                    self.strategy.add_position(price, date, reason)
                    position['qty'] += self.strategy.qty_step
                    print(f"\n  ADD: {reason} at ${price:.2f}")
                
                # Check for exits
                current_pnl = (price / position['entry_price'] - 1) * 100
                should_exit, exit_reason = self.strategy.should_exit(
                    price, date, iv, current_pnl
                )
                
                if should_exit:
                    pnl = self.strategy.close_position(price, date, exit_reason)
                    print(f"\n  EXIT: {exit_reason} at ${price:.2f} (PnL: {pnl:.1f}%)")
                    position = None
            
            # Update equity curve
            self.equity_curve.append({
                'date': date,
                'equity': current_capital,
                'price': price
            })
        
        print("\nBacktest complete")
    
    def to_markdown(self, output_file: str):
        """Generate a markdown report of the backtest results."""
        if not self.strategy.trades:
            print("No trades were executed in this backtest.")
            return
            
        # Generate summary statistics
        total_return = (self.equity_curve[-1]['equity'] / self.initial_capital - 1) * 100
        max_drawdown = self.calculate_max_drawdown()
        
        # Generate trade log
        trade_log = "\n## Trade Log\n\n"
        trade_log += "| Date | Action | Price | Qty | Reason | PnL % |\n"
        trade_log += "|------|--------|-------|-----|--------|-------|\n"
        
        for trade in self.strategy.trades:
            pnl = trade.get('pnl_pct', '')
            if pnl != '':
                pnl = f"{pnl:.1f}%"
            trade_log += f"| {trade['date'].strftime('%Y-%m-%d')} | {trade['action']} | ${trade['price']:.2f} | {trade['qty']} | {trade['reason']} | {pnl} |\n"
        
        # Generate report
        report = f"""# Backtest Report: {self.underlying} Risk Reversal

## Strategy Parameters
- **Underlying**: {self.underlying}
- **Start Date**: {self.start_date}
- **End Date**: {self.end_date}
- **Initial Capital**: ${self.initial_capital:,.2f}
- **Initial Contracts**: {self.strategy.qty_init}
- **Max Contracts**: {self.strategy.max_qty}
- **Long Call Strike**: ${self.strategy.long_call_strike}
- **Short Put Strike**: ${self.strategy.short_put_strike}
- **Add Trigger**: +${self.strategy.add_trigger}
- **Take Profit**: {self.strategy.take_profit_pct:.1f}x
- **Stop Loss**: ${self.strategy.stop_lvl} (with IV ≤ {self.strategy.iv_stop*100:.0f}%)

## Performance Summary
- **Total Return**: {total_return:.1f}%
- **Max Drawdown**: {max_drawdown:.1f}%
- **Number of Trades**: {len([t for t in self.strategy.trades if t['action'] == 'SELL'])}

{trade_log}
"""
        # Write to file
        with open(output_file, 'w') as f:
            f.write(report)
        
        print(f"Backtest report saved to {output_file}")
    
    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity curve."""
        if not self.equity_curve:
            return 0.0
            
        peak = self.equity_curve[0]['equity']
        max_drawdown = 0.0
        
        for point in self.equity_curve:
            if point['equity'] > peak:
                peak = point['equity']
            
            drawdown = (peak - point['equity']) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        return max_drawdown


if __name__ == "__main__":
    # Initialize the strategy
    strategy = RiskReversal(
        long_call_strike=420,
        short_put_strike=380,
        qty_init=5,
        qty_step=5,
        add_trigger=15,
        take_profit_pct=1.5,
        stop_lvl=385,
        iv_stop=0.10,
        max_qty=25,
        expiry="2025-06-13"
    )
    
    # Initialize and run the backtest
    bt = Backtester(
        underlying="MSTR",
        start="2025-05-12",
        end="2025-06-08",  # 5 trading days pre-expiry
        strategy=strategy
    )
    
    # Run the backtest and generate report
    bt.run()
    bt.to_markdown("backtests/mstr_may12_rr405/report.md")
