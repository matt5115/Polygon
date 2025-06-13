"""
Risk Reversal options strategy implementation.
"""
from datetime import date, datetime
from typing import List, Optional, Tuple, Dict, Any

class RiskReversal:
    """Risk Reversal options strategy."""
    
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
        self.positions: List[Tuple[float, int, date]] = []  # List of (entry_price, quantity, entry_date)
        self.last_add_price: Optional[float] = None
        self.trades: List[Dict[str, Any]] = []  # Track all trades for reporting
    
    def should_enter(self, price: float, date: date) -> Tuple[bool, str]:
        """Check if we should enter a new position."""
        if not self.positions and price > self.short_put_strike:
            return True, "Initial entry"
        return False, ""
    
    def should_add(self, price: float, date: date) -> Tuple[bool, str]:
        """Check if we should add to the position."""
        if not self.positions:
            return False, "No existing position"
            
        current_qty = sum(qty for _, qty, _ in self.positions)
        if current_qty >= self.max_qty:
            return False, "Max position size reached"
            
        if self.last_add_price is not None and price >= self.last_add_price + self.add_trigger:
            return True, f"Price moved +{self.add_trigger} above last add level"
            
        return False, ""
    
    def should_exit(
        self, 
        price: float, 
        date: date, 
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
            
        # Stop loss (updated to $389 as per requirements)
        if price <= self.stop_lvl:
            return True, f"Stop loss triggered at {price:.2f}"
        
        # Take profit
        if current_pnl is not None and current_pnl >= (self.take_profit_pct - 1) * 100:  # Convert to percentage
            return True, f"Take profit reached: {current_pnl:.1f}%"
            
        # Price target
        if price >= 440:  # Hard-coded from strategy
            return True, f"Price target reached: {price:.2f}"
            
        return False, ""
    
    def add_position(self, price: float, date: date, reason: str = ""):
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
    
    def close_position(self, price: float, date: date, reason: str = "") -> float:
        """Close all positions and return PnL percentage."""
        if not self.positions:
            return 0.0
            
        total_qty = sum(qty for _, qty, _ in self.positions)
        total_cost = sum(p * q for p, q, _ in self.positions)
        avg_entry = total_cost / total_qty
        pnl_pct = (price / avg_entry - 1) * 100  # PnL in %
        
        self.trades.append({
            'date': date,
            'action': 'SELL',
            'price': price,
            'qty': total_qty,
            'reason': reason,
            'pnl_pct': pnl_pct
        })
        
        # Reset state
        self.positions = []
        self.last_add_price = None
        
        return pnl_pct
