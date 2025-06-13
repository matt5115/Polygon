import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_option_contracts(underlying: str, exp_date: str, api_key: str):
    """Get all option contracts for a given underlying and expiration date."""
    url = f"https://api.polygon.io/v3/reference/options/contracts"
    params = {
        "underlying_ticker": underlying.upper(),
        "expiration_date": exp_date,
        "limit": 1000,
        "apiKey": api_key
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except Exception as e:
        print(f"Error getting option contracts: {str(e)}")
        return []

def get_option_snapshot(contract_ticker: str, as_of: str, api_key: str):
    """Get snapshot data for a specific option contract."""
    url = f"https://api.polygon.io/v3/snapshot/options/{contract_ticker}"
    params = {
        "as_of": as_of,
        "apiKey": api_key
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting snapshot for {contract_ticker}: {str(e)}")
        return None

def get_stock_price(ticker: str, date: str, api_key: str):
    """Get the adjusted close price of a stock on a specific date."""
    url = f"https://api.polygon.io/v1/open-close/{ticker.upper()}/{date}"
    params = {"adjusted": "true", "apiKey": api_key}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('close')
    except Exception as e:
        print(f"Error getting stock price: {str(e)}")
        return None

def find_atm_contracts(contracts, stock_price):
    """Find ATM call and put contracts from a list of contracts."""
    if not contracts:
        return None, None
    
    calls = [c for c in contracts if c.get('contract_type') == 'call']
    puts = [c for c in contracts if c.get('contract_type') == 'put']
    
    # Sort by distance from ATM
    calls.sort(key=lambda x: abs(x.get('strike_price', float('inf')) - stock_price))
    puts.sort(key=lambda x: abs(x.get('strike_price', float('inf')) - stock_price))
    
    return (
        calls[0]['ticker'] if calls else None, 
        puts[0]['ticker'] if puts else None
    )

def main():
    # Get API key
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("POLYGON_API_KEY not found in environment variables")
        return
    
    # Parameters
    ticker = "MSTR"
    target_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')  # ~May 12, 2025
    expiration_date = "2025-05-30"  # Example expiration date
    
    print(f"Fetching data for {ticker} on {target_date}...")
    
    # Get stock price on target date
    stock_price = get_stock_price(ticker, target_date, api_key)
    if stock_price is None:
        print(f"Could not get stock price for {ticker} on {target_date}")
        return
        
    print(f"{ticker} price on {target_date}: ${stock_price:.2f}")
    
    # Get all contracts for the expiration date
    print(f"\nFetching option contracts expiring on {expiration_date}...")
    contracts = get_option_contracts(ticker, expiration_date, api_key)
    
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
    call_snapshot = get_option_snapshot(call_ticker, target_date, api_key)
    put_snapshot = get_option_snapshot(put_ticker, target_date, api_key)
    
    # Extract and print IVs
    call_iv = call_snapshot.get('results', {}).get('implied_volatility') if call_snapshot else None
    put_iv = put_snapshot.get('results', {}).get('implied_volatility') if put_snapshot else None
    
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
