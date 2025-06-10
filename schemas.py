from pydantic import BaseModel, Field
from datetime import date
from typing import Optional
from models import TradeStatus

# Base schema with common fields
class TradeBase(BaseModel):
    ticker: str
    strategy: str  # "CSP" or "CC"
    strike: float
    expiry: date
    entry_price: Optional[float] = None
    premium: float
    delta: float
    annualized_yield: float
    pop: float  # Probability of Profit
    execution_source: str = "simulated"  # "simulated", "manual", or "api_live"
    live_trading_enabled: bool = False
    rationale: Optional[str] = None

# Schema for creating a new trade
class TradeCreate(TradeBase):
    pass

# Schema for updating a trade
class TradeUpdate(BaseModel):
    status: Optional[TradeStatus] = None
    result: Optional[float] = None
    rationale: Optional[str] = None

# Schema for returning trade data
class Trade(TradeBase):
    id: str
    status: TradeStatus
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True
        from_attributes = True  # Updated for Pydantic v2

# Schema for trade filters
class TradeFilters(BaseModel):
    ticker: Optional[str] = None
    strategy: Optional[str] = None
    status: Optional[TradeStatus] = None
    min_premium: Optional[float] = None
    min_yield: Optional[float] = None
    max_delta: Optional[float] = None
    min_delta: Optional[float] = None
