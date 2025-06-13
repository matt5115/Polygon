#!/usr/bin/env python3
"""
Real-time P&L and Risk Monitor for MSTR Options Trading

This script monitors open positions, tracks P&L, and enforces risk limits.
It can be run as a separate process or integrated into the trading daemon.
"""
import os
import sys
import time
import sqlite3
import logging
import pandas as pd
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('monitor.log')
    ]
)
logger = logging.getLogger(__name__)

class PositionMonitor:
    """Monitor positions and enforce risk limits."""
    
    def __init__(self, config: dict):
        self.config = config
        self.positions = {}
        self.risk_limits = {
            'max_loss': abs(float(config.get('max_loss_pct', -10.0)) / 100.0),  # Convert to decimal
            'max_drawdown': abs(float(config.get('max_drawdown_pct', -5.0)) / 100.0),
            'min_iv': float(config.get('min_iv', 0.08)),  # 8% minimum IV
            'max_position_size': int(config.get('max_position_size', 100))
        }
        self.db_path = os.path.join('data', 'trading.db')
        self._init_db()
    
    def _init_db(self):
        """Initialize the database if it doesn't exist."""
        os.makedirs('data', exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # Create tables if they don't exist
            c.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    qty REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    exit_price REAL,
                    exit_time TIMESTAMP,
                    pnl REAL,
                    pnl_pct REAL,
                    status TEXT DEFAULT 'OPEN',
                    strategy TEXT,
                    notes TEXT
                )
            ''')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS risk_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    symbol TEXT,
                    message TEXT NOT NULL,
                    severity TEXT DEFAULT 'WARNING',
                    resolved BOOLEAN DEFAULT 0
                )
            ''')
            conn.commit()
    
    def update_positions(self, positions: List[Dict]):
        """Update positions with latest data from exchange."""
        self.positions = {p['symbol']: p for p in positions}
        self._check_risk_limits()
    
    def _check_risk_limits(self):
        """Check all positions against risk limits."""
        for symbol, position in self.positions.items():
            # Check position P&L against max loss
            if position['unrealized_pnl_pct'] <= -abs(self.risk_limits['max_loss'] * 100):
                self._trigger_risk_event(
                    'MAX_LOSS_BREACH',
                    symbol,
                    f"Position P&L {position['unrealized_pnl_pct']:.2f}% "
                    f"exceeds max loss {self.risk_limits['max_loss']*100:.2f}%",
                    'CRITICAL'
                )
            
            # Check position size
            if abs(position['qty']) > self.risk_limits['max_position_size']:
                self._trigger_risk_event(
                    'POSITION_SIZE_LIMIT',
                    symbol,
                    f"Position size {position['qty']} exceeds maximum {self.risk_limits['max_position_size']}",
                    'WARNING'
                )
    
    def _trigger_risk_event(self, event_type: str, symbol: str, message: str, severity: str = 'WARNING'):
        """Record a risk event and trigger appropriate actions."""
        logger.log(
            getattr(logging, severity),
            f"{event_type} - {symbol}: {message}"
        )
        
        # Log to database
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO risk_events (event_type, symbol, message, severity)
                VALUES (?, ?, ?, ?)
            ''', (event_type, symbol, message, severity))
            conn.commit()
        
        # For critical events, trigger immediate action
        if severity == 'CRITICAL':
            self._handle_critical_event(event_type, symbol, message)
    
    def _handle_critical_event(self, event_type: str, symbol: str, message: str):
        """Handle critical risk events."""
        if 'MAX_LOSS_BREACH' in event_type:
            self._close_position(symbol, reason=f"Risk limit breached: {message}")
        elif 'IV_CRASH' in event_type:
            self._reduce_risk_exposure(symbol)
    
    def _close_position(self, symbol: str, reason: str):
        """Close a position immediately."""
        logger.warning(f"Closing position {symbol}: {reason}")
        # Implement actual position closing logic
        # This would call the exchange API to close the position
        
        # Update database
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                UPDATE positions 
                SET status = 'CLOSED', exit_time = CURRENT_TIMESTAMP, notes = ?
                WHERE symbol = ? AND status = 'OPEN'
            ''', (reason, symbol))
            conn.commit()
    
    def _reduce_risk_exposure(self, symbol: str):
        """Reduce risk exposure by closing a portion of the position."""
        logger.warning(f"Reducing exposure to {symbol} due to IV crash")
        # Implement position reduction logic
        
    def get_portfolio_summary(self) -> Dict:
        """Generate a summary of the current portfolio state."""
        total_pnl = sum(p['unrealized_pnl'] for p in self.positions.values())
        total_invested = sum(abs(p['qty'] * p['entry_price']) for p in self.positions.values())
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'num_positions': len(self.positions),
            'total_invested': total_invested,
            'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl / total_invested * 100) if total_invested > 0 else 0,
            'max_drawdown': self._calculate_max_drawdown(),
            'risk_status': self._get_risk_status()
        }
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown across all positions."""
        if not self.positions:
            return 0.0
        
        max_dd = 0.0
        for pos in self.positions.values():
            if 'max_drawdown_pct' in pos:
                max_dd = min(max_dd, pos['max_drawdown_pct'])
        
        return max_dd
    
    def _get_risk_status(self) -> Dict:
        """Get current risk status across all metrics."""
        status = {}
        portfolio = self.get_portfolio_summary()
        
        # Check portfolio-level metrics
        status['max_loss_breach'] = (
            portfolio['total_pnl_pct'] <= -abs(self.risk_limits['max_loss'] * 100)
        )
        status['max_drawdown_breach'] = (
            portfolio['max_drawdown'] <= -abs(self.risk_limits['max_drawdown'] * 100)
        )
        
        # Check position-level metrics
        status['iv_crash'] = any(
            p.get('iv', 0) < self.risk_limits['min_iv'] 
            for p in self.positions.values()
        )
        
        status['overall_risk'] = any(status.values())
        return status

def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file."""
    import yaml
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        sys.exit(1)

def main():
    """Main monitoring loop."""
    if len(sys.argv) < 2:
        print("Usage: monitor.py <config_file>")
        sys.exit(1)
    
    config = load_config(sys.argv[1])
    monitor = PositionMonitor(config)
    
    logger.info("Starting position monitor...")
    
    try:
        while True:
            # In a real implementation, this would fetch positions from the exchange
            # For now, we'll just log a heartbeat
            logger.debug("Monitoring positions...")
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        logger.info("Shutting down monitor...")
    except Exception as e:
        logger.error(f"Error in monitor: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
