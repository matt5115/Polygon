#!/usr/bin/env python3
"""
Live Trading Daemon for MSTR Options and CME MBT Futures Strategies.

Usage examples:

Options (existing behaviour):
    python live/trade_daemon.py --config config/live_strategy.yaml --mode options

Futures (new adapter):
    python live/trade_daemon.py --config config/futures_rules.yaml --mode futures
"""
import os
import sys
import time
import signal
import logging
import yaml
import asyncio
import pandas as pd
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

# Futures adapter added
try:
    from live.futures_adapter import FuturesAdapter
except ImportError:
    FuturesAdapter = None  # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trade_daemon.log')
    ]
)
logger = logging.getLogger(__name__)

class TradingHours:
    """Manage trading hours and market open/close times."""
    
    def __init__(self, start_time: str = "09:35", end_time: str = "15:55"):
        self.start_time = dt_time(*map(int, start_time.split(':')))
        self.end_time = dt_time(*map(int, end_time.split(':')))
    
    def is_market_open(self) -> bool:
        """Check if current time is within trading hours."""
        now = datetime.now().time()
        return self.start_time <= now <= self.end_time
    
    def seconds_until_open(self) -> float:
        """Calculate seconds until market opens."""
        now = datetime.now()
        today = now.date()
        
        # If before open time today
        open_time = datetime.combine(today, self.start_time)
        if now < open_time:
            return (open_time - now).total_seconds()
            
        # If after close time today, return seconds until open tomorrow
        tomorrow = today + timedelta(days=1)
        open_time = datetime.combine(tomorrow, self.start_time)
        return (open_time - now).total_seconds()

class TradeDaemon:
    """Main trading daemon class."""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.trading_hours = TradingHours(
            self.config.get('trading_hours_start', '09:35'),
            self.config.get('trading_hours_end', '15:55')
        )
        self.running = False
        
        # Initialize strategy
        self.strategy = self._init_strategy()
        
        # Initialize exchange connection
        self.exchange = self._init_exchange()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)
    
    def _init_strategy(self):
        """Initialize the selected trading strategy."""
        strategy_name = self.config.get('strategy', '')
        
        if 'risk_reversal' in strategy_name:
            from strategies.risk_reversal import RiskReversal
            return RiskReversal(
                qty_init=self.config.get('initial_qty', 5),
                qty_step=self.config.get('initial_qty', 5),
                max_qty=self.config.get('max_qty', 25),
                dte=30,
                put_strike_pct=0.95,  # 5% OTM
                call_strike_pct=1.05,  # 5% OTM
                stop_loss_pct=0.95,    # 5% stop
                take_profit_pct=1.20,  # 20% target
                add_trigger=self.config.get('add_trigger', 0.15),
                close_at_expiry=True
            )
        elif 'spread' in strategy_name:
            from strategies.debit_spread import DebitSpread
            # Parse strike percentages from strategy name
            strikes = [int(x) for x in strategy_name.split('_') if x.isdigit()]
            if len(strikes) >= 2:
                short_strike = strikes[0] / 1000  # Convert from bps
                long_strike = strikes[1] / 1000
            else:
                short_strike = 0.95  # Default values
                long_strike = 1.05
                
            return DebitSpread(
                qty_init=self.config.get('initial_qty', 5),
                qty_step=self.config.get('initial_qty', 5),
                max_qty=self.config.get('max_qty', 25),
                dte=30,
                short_strike_pct=short_strike,
                long_strike_pct=long_strike,
                stop_loss_pct=0.80,
                take_profit_pct=0.50,
                close_at_expiry=True
            )
        else:
            logger.error(f"Unknown strategy: {strategy_name}")
            sys.exit(1)
    
    def _init_exchange(self):
        """Initialize connection to the exchange."""
        # This is a placeholder - implement actual exchange connection
        class DummyExchange:
            def get_market_price(self, symbol: str) -> float:
                # Implement actual market data fetch
                return 0.0
                
            def place_order(self, symbol: str, qty: int, order_type: str, **kwargs) -> bool:
                # Implement actual order placement
                logger.info(f"Placing {order_type} order: {qty} {symbol}")
                return True
                
        return DummyExchange()
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received. Stopping...")
        self.running = False
    
    def run(self):
        """Main trading loop."""
        self.running = True
        logger.info("Starting trading daemon...")
        
        while self.running:
            try:
                if self.trading_hours.is_market_open():
                    self._trading_loop()
                else:
                    # Sleep until market opens
                    sleep_time = self.trading_hours.seconds_until_open()
                    logger.info(f"Market closed. Sleeping for {sleep_time/60:.1f} minutes...")
                    time.sleep(min(300, sleep_time))  # Sleep max 5 minutes
                    
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                time.sleep(60)  # Wait a minute before retrying
        
        logger.info("Trading daemon stopped.")
    
    def _trading_loop(self):
        """Execute one iteration of the trading loop."""
        # 1. Get current market data
        current_price = self.exchange.get_market_price(self.config['underlying'])
        
        # 2. Check for entry/exit signals
        signals = self.strategy.check_signals(current_price, datetime.now())
        
        # 3. Execute trades based on signals
        for signal in signals:
            self._execute_trade(signal)
        
        # 4. Monitor positions and manage risk
        self._monitor_positions()
        
        # 5. Sleep before next iteration
        time.sleep(60)  # Check every minute
    
    def _execute_trade(self, signal: Dict[str, Any]):
        """Execute a trade based on signal."""
        try:
            symbol = signal.get('symbol', self.config['underlying'])
            qty = signal.get('qty', 1)
            order_type = signal.get('order_type', self.config.get('order_type', 'LIMIT'))
            
            # Execute the order
            success = self.exchange.place_order(
                symbol=symbol,
                qty=qty,
                order_type=order_type,
                price=signal.get('limit_price'),
                stop_price=signal.get('stop_price')
            )
            
            if success:
                logger.info(f"Executed {signal.get('action', 'UNKNOWN')} order: {qty} {symbol}")
                # Update position tracking
                # Add to trade log
            else:
                logger.error(f"Failed to execute {signal.get('action')} order for {qty} {symbol}")
                
        except Exception as e:
            logger.error(f"Error executing trade: {e}", exc_info=True)
    
    def _monitor_positions(self):
        """Monitor open positions and manage risk."""
        # Check for stop-loss triggers
        # Check position P&L
        # Check portfolio-level risk limits
        pass

def _parse_cli():
    """Return (mode, config_path) from CLI args."""
    import argparse

    parser = argparse.ArgumentParser(description="Live trading daemon for options and futures")
    parser.add_argument("--config", default=None, help="Path to YAML configuration file")
    parser.add_argument("--mode", choices=["options", "futures"], default="options", help="Trading mode")
    args = parser.parse_args()

    if args.config is None:
        # default per-mode config
        args.config = (
            "config/futures_rules.yaml" if args.mode == "futures" else "config/live_strategy.yaml"
        )

    if not os.path.exists(args.config):
        logger.error("Config file not found: %s", args.config)
        sys.exit(1)

    return args.mode, args.config

def main():
    mode, config_path = _parse_cli()

    if mode == "futures":
        if FuturesAdapter is None:
            logger.error("FuturesAdapter module missing – ensure live/futures_adapter.py exists")
            sys.exit(1)
        cfg = yaml.safe_load(open(config_path, "r"))
        adapter = FuturesAdapter(
            symbol=cfg.get("symbol", "MBT"),
            contract=cfg.get("contract", "MBTM25"),
            md_ws=cfg["ironbeam"]["md_ws"],
        )
        logger.info("Starting FuturesAdapter (contract %s)", cfg.get("contract"))
        adapter.start()
        return

    # default options path
    daemon = TradeDaemon(config_path)
    daemon.run()

if __name__ == "__main__":
    main()
