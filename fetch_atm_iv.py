import os
from datetime import datetime, timedelta
from polygon import RESTClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def list_contracts(underlying: str, exp_date: str, client: RESTClient):
    """Return all option contracts for underlying expiring on exp_date (YYYY-MM-DD)."""
    try:
        contracts = client.get_reference_options_contracts(
            underlying_ticker=underlying.upper(),
            expiration_date=exp_date,
            limit=100  # adjust if needed
        )
        return contracts.results if hasattr(contracts, 'results') else []
    except Exception as e:
        print(f"Error listing contracts: {str(e)}")
        return []

def fetch_iv_snapshot(contract_ticker: str, as_of: str, client: RESTClient):
    """Snapshot greeks / IV for a single contract on a given date (YYYY-MM-DD)."""
    try:
        snapshot = client.get_snapshot_option_contract(
            underlying_asset=contract_ticker.split('-')[0],  # Extract underlying ticker
            option_contract=contract_ticker,
            as_of=as_of
        )
        return snapshot
    except Exception as e:
        print(f"Error fetching snapshot for {contract_ticker}: {str(e)}")
        return None

def find_atm_contracts(contracts, stock_price):
    """Find ATM call and put contracts from a list of contracts."""
    if not contracts:
        return None, None
    
    calls = [c for c in contracts if c.contract_type == 'call']
    puts = [c for c in contracts if c.contract_type == 'put']
    
    # Sort by distance from ATM
    calls.sort(key=lambda x: abs(x.strike_price - stock_price) if x.strike_price else float('inf'))
    puts.sort(key=lambda x: abs(x.strike_price - stock_price) if x.strike_price else float('inf'))
    
    return (calls[0].ticker if calls else None, 
            puts[0].ticker if puts else None)

def get_stock_price(ticker: str, date: str, client: RESTClient):
    """Get the closing price of a stock on a specific date."""
    try:
        # Get the daily bar for the specified date
        bars = client.get_daily_open_close_agg(
            ticker=ticker,
            date=date
        )
        return bars.close if hasattr(bars, 'close') else None
    except Exception as e:
        print(f"Error getting stock price: {str(e)}")
        return None

def main():
    # Initialize client
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("POLYGON_API_KEY not found in environment variables")
        return
        
    client = RESTClient(api_key)
    
    # Parameters
    ticker = "MSTR"
    target_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')  # ~May 12, 2025
    expiration_date = "2025-05-30"  # Example expiration date
    
    print(f"Fetching data for {ticker} on {target_date}...")
    
    # Get stock price on target date
    stock_price = get_stock_price(ticker, target_date, client)
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
