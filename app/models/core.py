"""Core ORM models (moved from legacy models.py).

Only change from original is swapping local `Base` declaration for
`from app.db import Base` so all models share a single metadata registry.
"""
from datetime import date
from uuid import uuid4
import enum

from sqlalchemy import Column, String, Float, Date, Enum, Boolean

from app.db import Base


class TradeStatus(str, enum.Enum):
    scanned = "scanned"
    forward_testing = "forward_testing"
    expired = "expired"
    executed = "executed"


class ExecutionSource(str, enum.Enum):
    simulated = "simulated"
    manual = "manual"
    api_live = "api_live"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    ticker = Column(String, nullable=False)
    strategy = Column(String, nullable=False)  # "CSP" or "CC"
    strike = Column(Float, nullable=False)
    expiry = Column(Date, nullable=False)
    entry_price = Column(Float, nullable=True)
    premium = Column(Float, nullable=False)
    delta = Column(Float, nullable=False)
    annualized_yield = Column(Float, nullable=False)
    pop = Column(Float, nullable=False)  # Probability of Profit
    status = Column(Enum(TradeStatus), default=TradeStatus.scanned)
    execution_source = Column(Enum(ExecutionSource), default=ExecutionSource.simulated)
    live_trading_enabled = Column(Boolean, default=False)
    result = Column(Float, nullable=True)
    rationale = Column(String, nullable=True)
    created_at = Column(Date, default=date.today, nullable=False)
    updated_at = Column(Date, default=date.today, onupdate=date.today, nullable=False)
