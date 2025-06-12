"""
Backtester module for options strategies with transaction cost and slippage modeling.
"""
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Type, Any, Literal
import pandas as pd
import numpy as np
from polygon import RESTClient
import os
from dotenv import load_dotenv

# Import accounting module
from backtest.accounting import TradeCostModel

# Load environment variables
load_dotenv()
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
if not POLYGON_API_KEY:
    raise ValueError("POLYGON_API_KEY environment variable not set")

class Backtester:
    """Backtesting engine for options strategies."""
    
    def __init__(
        self,
        underlying: str,
        start: str,
        end: str,
        strategy: 'Strategy',
        initial_capital: float = 1_400_000.0,  # $1.4M initial capital
        fee_per_contract: Optional[float] = None,
        slippage_pct: Optional[float] = None,
    ):
        """Initialize the backtester.
        
        Args:
            underlying: Ticker symbol of the underlying asset
            start: Start date in 'YYYY-MM-DD' format
            end: End date in 'YYYY-MM-DD' format
            strategy: Strategy instance to backtest
            initial_capital: Initial capital in USD
            fee_per_contract: Optional fee per contract (overrides environment)
            slippage_pct: Optional slippage as a decimal (e.g., 0.001 for 0.1%)
        """
        self.underlying = underlying.upper()
        self.start_date = datetime.strptime(start, "%Y-%m-%d").date()
        self.end_date = datetime.strptime(end, "%Y-%m-%d").date()
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.client = RESTClient(api_key=POLYGON_API_KEY)
        
        # Initialize cost model
        self.cost_model = TradeCostModel(
            fee_per_contract=fee_per_contract,
            slippage_pct=slippage_pct
        )
        
        # Results tracking
        self.equity_curve: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []
        self.total_pnl: float = 0.0
        self.max_drawdown: float = 0.0
        self.peak_equity: float = initial_capital
        self.total_commissions: float = 0.0
        self.total_slippage: float = 0.0
        
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
        
        # Get IV data (simplified - would need to fetch option chain data)
        df['iv'] = 0.0  # Placeholder - would need to fetch actual IV data
        
        return df.set_index('date').sort_index()
    
    def update_drawdown(self, current_equity: float):
        """Update max drawdown based on current equity."""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        drawdown = (current_equity - self.peak_equity) / self.peak_equity * 100
        self.max_drawdown = min(self.max_drawdown, drawdown)
    
    def _calculate_effective_price(
        self,
        price: float,
        qty: int,
        side: Literal['buy', 'sell']
    ) -> float:
        """Calculate effective price after accounting for fees and slippage."""
        return self.cost_model.apply_costs(price, qty, side)
    
    def _calculate_total_cost(
        self,
        price: float,
        qty: int,
        side: Literal['buy', 'sell']
    ) -> float:
        """Calculate total cost including fees and slippage."""
        return self.cost_model.calculate_total_cost(price, qty, side)
    
    def _execute_trade(
        self, 
        price: float, 
        date: date, 
        qty: int, 
        action: str, 
        reason: str = ""
    ) -> None:
        """Execute a trade and update the backtest state.
        
        Args:
            price: Price per share
            date: Trade date
            qty: Number of contracts (1 contract = 100 shares)
            action: 'BUY' or 'SELL'
            reason: Reason for the trade
        """
        if qty <= 0:
            return
            
        action = action.upper()
        side = 'buy' if action == 'BUY' else 'sell'
        
        # Calculate effective price and total cost with fees and slippage
        effective_price = self._calculate_effective_price(price, qty, side)
        total_cost = self._calculate_total_cost(price, qty, side)
        
        # Calculate commission and slippage
        commission = self.cost_model.fee_per_contract * qty
        slippage = abs(effective_price - price) * qty * 100  # Slippage in dollars
        
        # Update running totals
        self.total_commissions += commission
        self.total_slippage += slippage
        
        # Calculate net cost including all fees and slippage
        net_cost = total_cost
        if side == 'sell':
            self.total_pnl += net_cost  # Positive for sells (proceeds)
        else:
            self.total_pnl -= net_cost  # Negative for buys (cost)
        
        # Record the trade
        self.trades.append({
            'date': date,
            'action': action,
            'price': effective_price,  # Record effective price
            'qty': qty,
            'reason': reason,
            'cumulative_pnl': self.total_pnl,
            'commission': abs(commission) / (qty * 100),  # Per share
            'slippage': slippage / (qty * 100)  # Per share
        })
        
        # Update peak equity and max drawdown
        current_equity = self.initial_capital + self.total_pnl
        self.peak_equity = max(self.peak_equity, current_equity)
        drawdown = (self.peak_equity - current_equity) / self.peak_equity if self.peak_equity > 0 else 0.0
        self.max_drawdown = max(self.max_drawdown, drawdown)
    
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
        current_equity = self.initial_capital
        position = None
        
        for idx, row in data.iterrows():
            current_date = idx.date() if hasattr(idx, 'date') else idx
            price = row['close']
            iv = row.get('iv', 0.0)  # Default to 0 if IV not available
            
            # Print progress
            print(f"\rProcessing {current_date}: ${price:.2f}", end="")
            
            # Check for entry
            if not position:
                should_enter, reason = self.strategy.should_enter(price, current_date)
                if should_enter:
                    # Execute buy trade
                    self._execute_trade(
                        price=price,
                        date=current_date,
                        qty=self.strategy.qty_init,
                        action='BUY',
                        reason=reason
                    )
                    self.strategy.add_position(price, current_date, reason)
                    position = {
                        'entry_price': price,
                        'entry_date': current_date,
                        'qty': self.strategy.qty_init
                    }
                    print(f"\n  ENTRY: {reason} at ${price:.2f}")
            else:
                # Check for adds
                should_add, reason = self.strategy.should_add(price, current_date)
                if should_add:
                    # Execute additional buy trade
                    self._execute_trade(
                        price=price,
                        date=current_date,
                        qty=self.strategy.qty_step,
                        action='BUY',
                        reason=reason
                    )
                    self.strategy.add_position(price, current_date, reason)
                    position['qty'] += self.strategy.qty_step
                    print(f"\n  ADD: {reason} at ${price:.2f}")
                
                # Check for exits
                current_pnl = (price / position['entry_price'] - 1) * 100
                should_exit, exit_reason = self.strategy.should_exit(
                    price, current_date, iv, current_pnl
                )
                
                if should_exit:
                    # Execute sell trade for entire position
                    self._execute_trade(
                        price=price,
                        date=current_date,
                        qty=position['qty'],
                        action='SELL',
                        reason=exit_reason
                    )
                    pnl_pct = self.strategy.close_position(price, current_date, exit_reason)
                    self.total_pnl += (pnl_pct / 100) * (position['qty'] * 100 * position['entry_price']) / 100
                    current_equity = self.initial_capital + self.total_pnl
                    self.update_drawdown(current_equity)
                    print(f"\n  EXIT: {exit_reason} at ${price:.2f} (PnL: {pnl_pct:.1f}%)")
                    position = None
            
            # Update equity curve
            self.equity_curve.append({
                'date': current_date,
                'equity': current_equity,
                'price': price
            })
            
            # Update drawdown
            self.update_drawdown(current_equity)
        
        print("\nBacktest complete")
    
    def to_markdown(self, output_file: str):
        """Generate a markdown report of the backtest results with transaction costs and slippage."""
        if not self.strategy.trades:
            print("No trades were executed in this backtest.")
            return
            
        # Calculate performance metrics
        total_return_pct = (self.equity_curve[-1]['equity'] / self.initial_capital - 1) * 100
        
        # Calculate trade statistics
        trades_df = pd.DataFrame(self.strategy.trades)
        winning_trades = trades_df[trades_df['action'] == 'SELL'][trades_df['pnl_pct'] > 0]
        losing_trades = trades_df[trades_df['action'] == 'SELL'][trades_df['pnl_pct'] <= 0]
        total_trades = len(trades_df[trades_df['action'] == 'SELL'])
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        avg_win = winning_trades['pnl_pct'].mean() if not winning_trades.empty else 0
        avg_loss = losing_trades['pnl_pct'].mean() if not losing_trades.empty else 0
        profit_factor = abs(winning_trades['pnl_pct'].sum() / losing_trades['pnl_pct'].sum()) if not losing_trades.empty else float('inf')
        
        # Calculate total commissions and slippage
        total_commissions = sum(t.get('commission', 0) * t['qty'] * 100 for t in self.strategy.trades)
        total_slippage = sum(t.get('slippage', 0) * t['qty'] * 100 for t in self.strategy.trades)
        
        # Calculate net PnL after costs
        net_pnl = self.total_pnl - total_commissions - total_slippage
        net_return = (net_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        
        # Generate trade log with costs
        trade_log = "\n## Trade Log\n\n"
        trade_log += "| Date | Action | Price | Qty | Reason | PnL % | Commission | Slippage |\n"
        trade_log += "|------|--------|-------|-----|--------|-------|------------|----------|\n"
        
        for trade in self.strategy.trades:
            pnl = trade.get('pnl_pct', '')
            commission = trade.get('commission', 0) * trade['qty'] * 100
            slippage = trade.get('slippage', 0) * trade['qty'] * 100
            
            if pnl != '':
                pnl = f"{pnl:.1f}%"
            
            trade_log += (
                f"| {trade['date'].strftime('%Y-%m-%d')} | {trade['action']} | ${trade['price']:.2f} | "
                f"{trade['qty']} | {trade['reason']} | {pnl} | ${commission:.2f} | ${slippage:.2f} |\n"
            )
        
        # Generate report
        largest_win = winning_trades['pnl_pct'].max() if not winning_trades.empty else 0
        largest_loss = losing_trades['pnl_pct'].min() if not losing_trades.empty else 0
        
        report = f"""# Backtest Report: {self.underlying} {self.strategy.__class__.__name__}

## Strategy Parameters
- **Underlying**: {self.underlying}
- **Start Date**: {self.start_date}
- **End Date**: {self.end_date}
- **Initial Capital**: ${self.initial_capital:,.2f}
- **Final Equity**: ${self.equity_curve[-1]['equity']:,.2f}
- **Gross Return**: {total_return_pct:.2f}%
- **Net Return (after costs)**: {net_return:.2f}%
- **Max Drawdown**: {self.max_drawdown:.2f}%
- **Total PnL (Gross)**: ${self.total_pnl:,.2f}
- **Total PnL (Net)**: ${net_pnl:,.2f}
- **Number of Trades**: {total_trades}

## Performance Summary
- **Win Rate**: {win_rate:.1f}%
- **Average Win**: {avg_win:.2f}%
- **Average Loss**: {avg_loss:.2f}%
- **Profit Factor**: {profit_factor:.2f}
- **Total Commissions**: ${total_commissions:,.2f}
- **Total Slippage**: ${total_slippage:,.2f}
- **Total Costs (Commissions + Slippage)**: ${total_commissions + total_slippage:,.2f}
- **Costs as % of Capital**: {(total_commissions + total_slippage) / self.initial_capital * 100:.2f}%

## Trade Statistics
- **Total Trades**: {total_trades}
- **Winning Trades**: {len(winning_trades)}
- **Losing Trades**: {len(losing_trades)}
- **Largest Winning Trade**: {largest_win:.2f}%
- **Largest Losing Trade**: {largest_loss:.2f}%

{trade_log}"""
        # Write to file
        with open(output_file, 'w') as f:
            f.write(report)
        
        print(f"Backtest report saved to {output_file}")


class Strategy:
    """Base class for all trading strategies."""
    def should_enter(self, price: float, date: date) -> Tuple[bool, str]:
        """Check if we should enter a new position."""
        raise NotImplementedError
    
    def should_add(self, price: float, date: date) -> Tuple[bool, str]:
        """Check if we should add to the position."""
        raise NotImplementedError
    
    def should_exit(
        self, 
        price: float, 
        date: date, 
        iv: Optional[float] = None,
        current_pnl: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Check if we should exit the position."""
        raise NotImplementedError
    
    def add_position(self, price: float, date: date, reason: str = ""):
        """Add a new position."""
        raise NotImplementedError
    
    def close_position(self, price: float, date: date, reason: str = "") -> float:
        """Close all positions and return PnL percentage."""
        raise NotImplementedError
