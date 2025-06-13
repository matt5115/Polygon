"""
Call Debit Spread options strategy implementation.
"""
from datetime import date, datetime
from typing import List, Optional, Tuple, Dict, Any

class CallDebitSpread:
    """Call Debit Spread options strategy."""
    
    def __init__(
        self,
        long_strike: float,
        short_strike: float,
        qty: int = 10,
        expiry: str = "2025-06-13",  # Expiry date in YYYY-MM-DD
        **kwargs  # Accept additional arguments for compatibility
    ):
        """Initialize the call debit spread strategy.
        
        Args:
            long_strike: Strike price for long calls
            short_strike: Strike price for short calls
            qty: Number of spreads to trade
            expiry: Option expiration date (YYYY-MM-DD)
        """
        self.long_strike = long_strike
        self.short_strike = short_strike
        self.qty = qty
        self.qty_init = qty  # For compatibility with backtester
        self.expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
        
        # For compatibility with backtester's position tracking
        self.positions = []  # List of (entry_price, quantity, entry_date)
        
        # State variables
        self.entry_price: Optional[float] = None
        self.entry_date: Optional[date] = None
        self.last_add_price: Optional[float] = None  # For compatibility
        self.trades: List[Dict[str, Any]] = []  # Track all trades for reporting
        self.positions: List[Tuple[float, int, date]] = []  # For compatibility
        
        # Calculate max loss and max gain
        self.spread_width = short_strike - long_strike
        self.max_loss = -qty * 100  # Max loss is the net debit paid (simplified)
        self.max_gain = qty * (self.spread_width * 100) + self.max_loss  # Max gain if both options expire ITM
    
    def should_enter(self, price: float, current_date: date) -> Tuple[bool, str]:
        """Check if we should enter a new position."""
        if self.entry_price is None and current_date >= self.expiry:
            return False, "Expiry date has passed"
            
        if self.entry_price is None:
            return True, "Initial entry"
        return False, ""
    
    def should_add(self, price: float, date: date) -> Tuple[bool, str]:
        """Check if we should add to the position."""
        # No scaling for this strategy
        return False, "No scaling allowed for debit spread"
    
    def should_exit(
        self, 
        price: float, 
        current_date: date, 
        iv: Optional[float] = None,
        current_pnl: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Check if we should exit the position."""
        if self.entry_price is None:
            return False, "No position to exit"
            
        # Time-based exit (at expiry)
        if current_date >= self.expiry:
            return True, "Expiration reached"
            
        # Take profit at 150% of max gain potential (simplified)
        if current_pnl is not None and current_pnl >= 1.5 * self.max_gain:
            return True, f"Take profit reached: {current_pnl:.1f}"
            
        # Stop loss at 50% of max loss (simplified)
        if current_pnl is not None and current_pnl <= 0.5 * self.max_loss:
            return True, f"Stop loss triggered: {current_pnl:.1f}"
            
        return False, ""
    
    def add_position(self, price: float, date: date, reason: str = ""):
        """Add a new position."""
        if self.entry_price is not None:
            return  # Already in a position
            
        self.entry_price = price
        self.entry_date = date
        self.positions = [(price, self.qty, date)]  # For compatibility
        
        self.trades.append({
            'date': date,
            'action': 'BUY',
            'price': price,
            'qty': self.qty,
            'reason': reason or "Initial entry"
        })
    
    def close_position(self, price: float, date: date, reason: str = "") -> float:
        """Close all positions and return PnL."""
        if self.entry_price is None and not self.positions:
            return 0.0
            
        # Calculate PnL in dollars (simplified)
        entry_price = self.entry_price if self.entry_price is not None else self.positions[0][0]
        pnl = (price - entry_price) * self.qty * 100
        pnl_pct = (price / entry_price - 1) * 100  # PnL in %
        
        self.trades.append({
            'date': date,
            'action': 'SELL',
            'price': price,
            'qty': self.qty,
            'reason': reason,
            'pnl_pct': pnl_pct
        })
        
        # Reset state
        self.entry_price = None
        self.entry_date = None
        self.positions = []
        
        return pnl_pct  # Return percentage for consistency with backtester
