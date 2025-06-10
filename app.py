from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional
import models
import schemas
from db import init_db, get_db

# Initialize FastAPI app
app = FastAPI(title="Options Trade Manager",
             description="API for managing options trades",
             version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def on_startup():
    init_db()

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Create trade endpoint
@app.post("/trades/", response_model=schemas.Trade)
def create_trade(trade: schemas.TradeCreate, db: Session = Depends(get_db)):
    """
    Create a new trade with execution source validation
    """
    # Block any API live trade unless explicitly enabled and verified
    if trade.execution_source == "api_live" and not trade.live_trading_enabled:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "live_trading_not_enabled",
                "message": "Live trading must be explicitly enabled for API live trades"
            }
        )
    
    db_trade = models.Trade(**trade.dict())
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade

# Get all trades
@app.get("/trades/", response_model=List[schemas.Trade])
def read_trades(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve all trades with pagination
    """
    return db.query(models.Trade).offset(skip).limit(limit).all()

# Get trade by ID
@app.get("/trades/{trade_id}", response_model=schemas.Trade)
def read_trade(trade_id: str, db: Session = Depends(get_db)):
    """
    Get a specific trade by ID
    """
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade

# Update trade status
@app.patch("/trades/{trade_id}", response_model=schemas.Trade)
def update_trade_status(
    trade_id: str, 
    trade_update: schemas.TradeUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update a trade's status and other fields
    """
    db_trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if db_trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    update_data = trade_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_trade, key, value)
    
    db.commit()
    db.refresh(db_trade)
    return db_trade

# Delete trade
@app.delete("/trades/{trade_id}")
def delete_trade(trade_id: str, db: Session = Depends(get_db)):
    """
    Delete a trade
    """
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    db.delete(trade)
    db.commit()
    return {"message": "Trade deleted successfully"}
