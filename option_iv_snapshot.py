#!/usr/bin/env python3
"""Fetch and analyze option IV snapshots from Polygon.io.

This script demonstrates how to use the polygon_helpers module to fetch
and analyze option implied volatility data for a given stock and date.
"""
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from polygon import RESTClient
from utils.polygon_helpers import (
    list_contracts,
    fetch_iv_snapshot,
    get_stock_price,
    find_atm_contracts
)

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize client
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("POLYGON_API_KEY not found in environment variables")
        return
    
    client = RESTClient(api_key)
    
    # Parameters
    ticker = "MSTR"
    target_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')  # ~May 12, 2025
    expiration_date = "2025-06-13"  # Next available expiration
    
    print(f"Fetching data for {ticker} on {target_date}...")
    
    # Get stock price on target date
    stock_price = get_stock_price(ticker, target_date, api_key)
    if stock_price is None:
        print(f"Could not get stock price for {ticker} on {target_date}")
        return
        
    print(f"{ticker} price on {target_date}: ${stock_price:.2f}")
    
    # Get all contracts for the expiration date
    print(f"\nFetching option contracts expiring on {expiration_date}...")
    contracts = list_contracts(ticker, expiration_date, client)
    
    if not contracts:
        print(f"No option contracts found for {ticker} expiring on {expiration_date}")
        return
    
    print(f"Found {len(contracts)} contracts")
    
    # Find ATM call and put
    call_ticker, put_ticker = find_atm_contracts(contracts, stock_price)
    
    if not call_ticker or not put_ticker:
        print("Could not find ATM call and/or put contracts")
        return
    
    print(f"\nATM Call: {call_ticker}")
    print(f"ATM Put:  {put_ticker}")
    
    # Get IV snapshots
    print(f"\nFetching IV snapshots for {target_date}...")
    call_snapshot = fetch_iv_snapshot(call_ticker, target_date, client)
    put_snapshot = fetch_iv_snapshot(put_ticker, target_date, client)
    
    # Extract and print IVs
    call_iv = getattr(call_snapshot, 'implied_volatility', None) if call_snapshot else None
    put_iv = getattr(put_snapshot, 'implied_volatility', None) if put_snapshot else None
    
    if call_iv is not None and put_iv is not None:
        print(f"\nATM Call IV: {call_iv*100:.1f}%")
        print(f"ATM Put IV:  {put_iv*100:.1f}%")
        print(f"IV Skew (Put - Call): {(put_iv - call_iv)*100:+.1f}%")
    else:
        print("\nCould not retrieve IV data. Raw snapshots:")
        print(f"Call: {call_snapshot}")
        print(f"Put:  {put_snapshot}")

if __name__ == "__main__":
    main()
