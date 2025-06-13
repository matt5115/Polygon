"""
Transaction cost and slippage modeling for backtesting.
"""
from typing import Optional, Literal
import os

# Default values that can be overridden by environment variables
DEFAULT_OPTION_FEE = 0.65  # $0.65 per contract
DEFAULT_SLIPPAGE_PCT = 0.1  # 0.1% slippage


def get_option_fee() -> float:
    """Get the per-contract fee from environment or use default."""
    return float(os.getenv('OPTION_FEE', DEFAULT_OPTION_FEE))


def get_slippage_pct() -> float:
    """Get the slippage percentage from environment or use default."""
    return float(os.getenv('SLIPPAGE_PCT', DEFAULT_SLIPPAGE_PCT)) / 100.0  # Convert to decimal


def apply_fee(price: float, contracts: int, fee_per_contract: Optional[float] = None) -> float:
    """Apply transaction fees to a trade.
    
    Args:
        price: The base price per share
        contracts: Number of option contracts (each contract is 100 shares)
        fee_per_contract: Optional override for fee per contract
        
    Returns:
        Adjusted price per share after fees
    """
    if fee_per_contract is None:
        fee_per_contract = get_option_fee()
    
    if contracts <= 0:
        return price
        
    total_fee = fee_per_contract * contracts
    total_shares = contracts * 100  # Each contract is 100 shares
    fee_per_share = total_fee / total_shares
    
    # Apply fee to sell orders, not buy orders
    return price + fee_per_share


def apply_slippage(
    price: float, 
    side: Literal['buy', 'sell'], 
    slippage_pct: Optional[float] = None
) -> float:
    """Apply slippage to a trade.
    
    Args:
        price: The base price per share
        side: 'buy' or 'sell'
        slippage_pct: Optional override for slippage percentage (as decimal, e.g., 0.001 for 0.1%)
        
    Returns:
        Adjusted price per share after slippage
    """
    if slippage_pct is None:
        slippage_pct = get_slippage_pct()
    
    slippage = price * slippage_pct
    
    if side.lower() == 'buy':
        return price + slippage
    elif side.lower() == 'sell':
        return price - slippage
    else:
        raise ValueError(f"Invalid side: {side}. Must be 'buy' or 'sell'")


def calculate_total_cost(
    price: float,
    contracts: int,
    side: Literal['buy', 'sell'],
    fee_per_contract: Optional[float] = None,
    slippage_pct: Optional[float] = None
) -> float:
    """Calculate total cost including fees and slippage.
    
    Args:
        price: Base price per share
        contracts: Number of option contracts
        side: 'buy' or 'sell'
        fee_per_contract: Optional override for fee per contract
        slippage_pct: Optional override for slippage percentage (as decimal)
        
    Returns:
        Total cost including all fees and slippage
    """
    if fee_per_contract is None:
        fee_per_contract = get_option_fee()
    if slippage_pct is None:
        slippage_pct = get_slippage_pct()
        
    # Calculate total shares and fees
    total_shares = contracts * 100
    total_fee = fee_per_contract * contracts
    
    # Apply slippage to the base price
    if side == 'buy':
        # For buys, we pay more due to slippage
        slipped_price = price * (1 + slippage_pct)
        # Add fees to the total cost
        total_cost = (slipped_price * total_shares) + total_fee
        return total_cost
    else:  # sell
        # For sells, we receive less due to slippage
        slipped_price = price * (1 - slippage_pct)
        # Subtract fees from the proceeds
        total_proceeds = (slipped_price * total_shares) - total_fee
        return -total_proceeds  # Negative for sells


class TradeCostModel:
    """Helper class to manage trade costs and slippage."""
    
    def __init__(
        self,
        fee_per_contract: Optional[float] = None,
        slippage_pct: Optional[float] = None
    ):
        """Initialize with custom fee and slippage settings."""
        self.fee_per_contract = fee_per_contract
        self.slippage_pct = slippage_pct
    
    def apply_costs(
        self,
        price: float,
        contracts: int,
        side: Literal['buy', 'sell']
    ) -> float:
        """Apply all costs to a trade and return the effective price."""
        # Get slippage percentage, defaulting to class default if not set
        slippage = self.slippage_pct if self.slippage_pct is not None else get_slippage_pct()
        
        # Apply slippage first
        slipped = price * (1 + slippage) if side == 'buy' else price * (1 - slippage)
        
        # Then apply fees (add for buys, subtract for sells)
        total_fee = (self.fee_per_contract if self.fee_per_contract is not None else get_option_fee()) * contracts
        total_shares = contracts * 100
        fee_per_share = total_fee / total_shares
        
        return slipped + (fee_per_share if side == 'buy' else -fee_per_share)
    
    def calculate_total_cost(
        self,
        price: float,
        contracts: int,
        side: Literal['buy', 'sell']
    ) -> float:
        """Calculate total cost including all fees and slippage."""
        return calculate_total_cost(
            price=price,
            contracts=contracts,
            side=side,
            fee_per_contract=self.fee_per_contract,
            slippage_pct=self.slippage_pct
        )
