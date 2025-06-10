"""
Tests for trade creation with execution metadata
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import app, get_db
from db import Base
from models import ExecutionSource

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_trades.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def test_create_simulated_trade():
    """Test creating a simulated trade"""
    trade_data = {
        "ticker": "AAPL",
        "strategy": "CSP",
        "strike": 180.0,
        "expiry": "2025-06-20",
        "entry_price": 185.5,
        "premium": 2.5,
        "delta": 0.25,
        "annualized_yield": 0.3,
        "pop": 0.75,
        "execution_source": "simulated",
        "live_trading_enabled": False,
        "rationale": "Test simulated trade"
    }
    
    response = client.post("/trades/", json=trade_data)
    assert response.status_code == 201
    result = response.json()
    assert result["ticker"] == "AAPL"
    assert result["execution_source"] == "simulated"
    assert result["live_trading_enabled"] is False

def test_create_live_trade_without_permission():
    """Test that live trading is blocked without explicit permission"""
    trade_data = {
        "ticker": "MSFT",
        "strategy": "CC",
        "strike": 420.0,
        "expiry": "2025-07-19",
        "entry_price": 415.0,
        "premium": 8.50,
        "delta": 0.30,
        "annualized_yield": 0.25,
        "pop": 0.70,
        "execution_source": "api_live",  # Live trading
        "live_trading_enabled": False,   # But not enabled
        "rationale": "Should be blocked"
    }
    
    response = client.post("/trades/", json=trade_data)
    assert response.status_code == 400
    assert "live_trading_not_enabled" in response.text

def test_create_live_trade_with_permission():
    """Test creating a live trade with proper permission"""
    trade_data = {
        "ticker": "GOOGL",
        "strategy": "CSP",
        "strike": 2800.0,
        "expiry": "2025-08-20",
        "entry_price": 2850.0,
        "premium": 28.50,
        "delta": 0.20,
        "annualized_yield": 0.35,
        "pop": 0.80,
        "execution_source": "api_live",
        "live_trading_enabled": True,  # Explicitly enabled
        "rationale": "Live trade test"
    }
    
    response = client.post("/trades/", json=trade_data)
    assert response.status_code == 201
    result = response.json()
    assert result["ticker"] == "GOOGL"
    assert result["execution_source"] == "api_live"
    assert result["live_trading_enabled"] is True

# Clean up after tests
@pytest.fixture(scope="session", autouse=True)
def cleanup():
    """Clean up the test database after all tests are done"""
    yield
    import os
    if os.path.exists("test_trades.db"):
        os.remove("test_trades.db")
