"""
Trade Simulator Module

This module provides functionality to simulate options trades (CSPs and covered calls)
for both backtesting and forward testing scenarios using Polygon.io data.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Optional, Union, Tuple
import requests
from dateutil.parser import parse as parse_date

# Custom exceptions
class SimulationError(Exception):
    """Raised when there's an error during trade simulation."""
    pass

class PolygonAPIError(Exception):
    """Raised when there's an error with the Polygon.io API."""
    pass

def get_historical_underlying_data(symbol: str, start_date: str, end_date: str) -> Dict[str, float]:
    """
    Fetch historical underlying price data from Polygon.io
    
    Args:
        symbol: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Dictionary with dates as keys and prices as values
    """
    # This is a placeholder - implement actual API call to Polygon.io
    # For now, return mock data
    return {
        "2025-06-10": 200.0,
        "2025-06-11": 201.5,
        "2025-06-12": 199.8,
        "2025-06-13": 202.4
    }

def calculate_black_scholes_greeks() -> Dict[str, float]:
    """
    Calculate option greeks using Black-Scholes model
    
    Returns:
        Dictionary containing delta, gamma, theta, vega, rho
    """
    # Placeholder for Black-Scholes implementation
    return {
        'delta': 0.35,
        'gamma': 0.05,
        'theta': -0.05,
        'vega': 0.12,
        'rho': 0.03
    }

def simulate_trade(
    symbol: str,
    option_type: str,         # "put" or "call"
    strike_price: float,
    expiration: str,          # ISO date string (YYYY-MM-DD)
    entry_price: float,       # Premium received
    entry_date: str,          # ISO date string (YYYY-MM-DD)
    underlying_price: float,  # Underlying at time of entry
    quantity: int = 1,
    simulate_forward: bool = True  # False = backtest mode
) -> dict:
    """
    Simulate an options trade (CSP or covered call) for backtesting or forward testing.
    
    Args:
        symbol: Ticker symbol (e.g., "AAPL")
        option_type: "put" or "call"
        strike_price: Option strike price
        expiration: Option expiration date (YYYY-MM-DD)
        entry_price: Premium received per contract
        entry_date: Trade entry date (YYYY-MM-DD)
        underlying_price: Underlying price at entry
        quantity: Number of contracts
        simulate_forward: If True, simulates forward in time; if False, backtests
        
    Returns:
        Dictionary containing trade simulation results
        
    Raises:
        SimulationError: If there's an error during simulation
        PolygonAPIError: If there's an error with the Polygon.io API
    """
    # Input validation
    option_type = option_type.lower()
    if option_type not in ['put', 'call']:
        raise ValueError("option_type must be 'put' or 'call'")
    
    if strike_price <= 0 or entry_price <= 0 or underlying_price <= 0:
        raise ValueError("Prices must be positive")
    
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    
    try:
        exp_date = parse_date(expiration).date()
        entry_date_dt = parse_date(entry_date).date()
        today = datetime.now().date()
        
        if exp_date <= entry_date_dt:
            raise ValueError("Expiration date must be after entry date")
            
        if entry_date_dt > today and not simulate_forward:
            raise ValueError("Entry date cannot be in the future for backtesting")
            
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid date format: {e}")
    
    # Calculate basic trade metrics
    days_to_expiration = (exp_date - entry_date_dt).days
    if days_to_expiration == 0:
        days_to_expiration = 1  # Avoid division by zero
    
    # Calculate breakeven
    if option_type == 'put':
        breakeven = strike_price - entry_price
    else:  # call
        breakeven = strike_price + entry_price
    
    # Calculate max profit/loss
    max_profit = entry_price * 100 * quantity  # Premium received
    
    if option_type == 'put':
        max_loss = (strike_price * 100 * quantity) - (entry_price * 100 * quantity)
    else:  # call
        max_loss = float('inf')  # Unlimited loss potential for naked calls
    
    # Calculate yields
    realized_yield = (entry_price / strike_price) * 100
    annualized_yield = (realized_yield / days_to_expiration) * 365
    
    # Simulate the trade
    if simulate_forward:
        # Forward simulation - use models to estimate outcomes
        greeks = calculate_black_scholes_greeks()
        probability_of_profit = 0.7  # Placeholder - should be calculated
        
        # For forward testing, we'll make some assumptions
        exit_price = entry_price * 0.5  # Exit at 50% profit
        held_days = days_to_expiration // 2  # Assume exiting halfway
        
        # Simulate final underlying price (could be more sophisticated)
        if option_type == 'put':
            underlying_final = underlying_price * 1.02  # 2% increase
        else:  # call
            underlying_final = underlying_price * 0.98  # 2% decrease
            
        expired_itm = (
            (option_type == 'put' and underlying_final < strike_price) or
            (option_type == 'call' and underlying_final > strike_price)
        )
        
        # Calculate max drawdown (simplified)
        max_drawdown = -2.5  # Placeholder - should be calculated
        
    else:
        # Backtest - use historical data
        try:
            historical_data = get_historical_underlying_data(
                symbol, entry_date, expiration
            )
            
            if not historical_data:
                raise SimulationError("No historical data available for the specified period")
                
            # Get the last available price as final price
            underlying_final = list(historical_data.values())[-1]
            
            # Calculate if expired ITM
            expired_itm = (
                (option_type == 'put' and underlying_final < strike_price) or
                (option_type == 'call' and underlying_final > strike_price)
            )
            
            # Calculate exit price (simplified - could be based on historical bid/ask)
            if expired_itm:
                if option_type == 'put':
                    exit_price = max(strike_price - underlying_final, 0.01)
                else:  # call
                    exit_price = max(underlying_final - strike_price, 0.01)
            else:
                exit_price = 0.01  # Assume closed at $0.01 if OTM
                
            # Calculate actual held days (simplified)
            held_days = min(30, days_to_expiration)  # Assume 30-day hold or to expiration
            
            # Calculate max drawdown (simplified)
            max_price = max(historical_data.values())
            min_price = min(historical_data.values())
            
            if option_type == 'put':
                max_drawdown = ((min_price - underlying_price) / underlying_price) * 100
            else:  # call
                max_drawdown = ((underlying_price - max_price) / underlying_price) * 100
                
            # Calculate probability of profit (simplified)
            probability_of_profit = 0.7  # Placeholder - could be based on delta
            
        except Exception as e:
            raise SimulationError(f"Error in backtest simulation: {str(e)}")
    
    # Determine if assignment would have occurred
    assigned = False
    if not simulate_forward and expired_itm:
        assigned = True
    
    # Prepare and return results
    result = {
        "symbol": symbol.upper(),
        "option_type": option_type,
        "strike": strike_price,
        "expiration": expiration,
        "entry_date": entry_date,
        "entry_price": round(entry_price, 2),
        "exit_price": round(exit_price, 2),
        "realized_yield": round(realized_yield, 2),
        "annualized_yield": round(annualized_yield, 2),
        "held_days": held_days,
        "expired_ITM": expired_itm,
        "assigned": assigned,
        "underlying_final_price": round(underlying_final, 2),
        "max_drawdown": round(max_drawdown, 2),
        "probability_of_profit": round(probability_of_profit, 2),
        "breakeven": round(breakeven, 2),
        "max_profit": round(max_profit, 2),
        "max_loss": round(max_loss, 2) if max_loss != float('inf') else float('inf')
    }
    
    return result

def simulate_recommended_trades(trades: list, underlying_prices: dict, simulate_forward: bool = True) -> list:
    """
    Enhance a list of recommended trades with simulation data.
    
    Args:
        trades: List of trade dictionaries, each containing at least:
            - 'symbol': Ticker symbol
            - 'option_type': 'put' or 'call'
            - 'strike_price': Option strike price
            - 'expiration': Expiration date (YYYY-MM-DD)
            - 'mid_price': Option premium (mid price)
            - 'underlying_price': Current underlying price
        underlying_prices: Dictionary mapping ticker symbols to current prices
        simulate_forward: Whether to simulate forward or backtest
        
    Returns:
        List of enhanced trade dictionaries with simulation results
    """
    if not trades:
        return []
        
    enhanced_trades = []
    
    for trade in trades:
        try:
            # Skip if already has simulation data
            if 'simulation' in trade:
                enhanced_trades.append(trade)
                continue
                
            # Get current price if not provided
            underlying_price = trade.get('underlying_price') or underlying_prices.get(trade['symbol'])
            if not underlying_price:
                print(f"⚠️ Could not find price for {trade['symbol']}, skipping simulation")
                trade['simulation'] = {'error': 'Missing underlying price'}
                enhanced_trades.append(trade)
                continue
                
            # Run simulation
            simulation = simulate_trade(
                symbol=trade['symbol'],
                option_type=trade['option_type'],
                strike_price=trade['strike_price'],
                expiration=trade['expiration'],
                entry_price=trade['mid_price'],
                entry_date=datetime.now().strftime('%Y-%m-%d'),
                underlying_price=underlying_price,
                quantity=1,  # Per contract
                simulate_forward=simulate_forward
            )
            
            # Add simulation results to trade
            trade['simulation'] = simulation
            enhanced_trades.append(trade)
            
            # Add small delay to avoid rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            print(f"⚠️ Error simulating trade for {trade.get('symbol', 'unknown')}: {str(e)}")
            trade['simulation'] = {'error': str(e)}
            enhanced_trades.append(trade)
    
    return enhanced_trades

# Example usage
if __name__ == "__main__":
    # Example: Simulate a CSP on AAPL
    try:
        result = simulate_trade(
            symbol="AAPL",
            option_type="put",
            strike_price=195.0,
            expiration="2025-07-18",
            entry_price=1.58,
            entry_date="2025-06-10",
            underlying_price=200.0,
            quantity=1,
            simulate_forward=True
        )
        
        # Print results
        print("\nTrade Simulation Results:")
        print("-" * 40)
        for key, value in result.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
            
    except Exception as e:
        print(f"Error simulating trade: {e}")
