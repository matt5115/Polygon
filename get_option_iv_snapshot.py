from polygon import RESTClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Polygon client
CLIENT = RESTClient(os.getenv('POLYGON_API_KEY'))

def get_chain_snapshot(underlying: str, as_of: str):
    """Return Polygon option-chain snapshot for a given date (YYYY-MM-DD)."""
    try:
        return CLIENT.get_snapshot_option_chain(
            underlying,
            as_of=as_of  # historical date
        )
    except Exception as e:
        print(f"Error fetching option chain: {str(e)}")
        return None

def filter_contracts(chain_json, exp_date=None, moneyness="ATM"):
    """
    Pull ATM calls & puts for a single expiration.
    `moneyness="ATM"` grabs the contract whose strike is closest to lastPrice.
    If exp_date is None, returns all contracts sorted by expiration and strike.
    """
    if not chain_json or "results" not in chain_json:
        print("No results in chain JSON")
        return None, None
        
    # Filter by expiration if provided
    contracts = chain_json["results"]
    if exp_date:
        contracts = [c for c in contracts 
                    if c["details"]["expiration_date"] == exp_date]
    
    if not contracts:
        print(f"No contracts found for expiration {exp_date}")
        return None, None
    
    # Get underlying price
    ul_price = chain_json["underlying_asset"]["last_price"]
    print(f"Underlying price: ${ul_price:.2f}")
    
    # Sort by distance to underlying price (ATM first)
    contracts.sort(key=lambda c: abs(c["details"]["strike_price"] - ul_price))
    
    # Get ATM call and put
    call = next((c for c in contracts if c["details"]["type"] == "call"), None)
    put = next((c for c in contracts if c["details"]["type"] == "put"), None)
    
    return call, put

def main():
    # Set parameters
    ticker = "MSTR"
    target_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    print(f"Fetching option chain for {ticker} on {target_date}...")
    
    # Get the option chain snapshot
    chain = get_chain_snapshot(ticker, target_date)
    if not chain:
        print("Failed to fetch option chain")
        return
    
    # Get unique expiration dates
    expirations = sorted(list(set(
        c["details"]["expiration_date"] 
        for c in chain["results"]
    )))
    
    print(f"\nAvailable expirations: {', '.join(expirations[:5])}{'...' if len(expirations) > 5 else ''}")
    
    # If no expirations found, try getting the first 3
    if not expirations:
        print("No expirations found. Trying to fetch first 3 active expirations...")
        return
    
    # Get ATM calls and puts for the first 3 expirations
    for exp in expirations[:3]:
        print(f"\n=== {ticker} {exp} ===")
        call, put = filter_contracts(chain, exp)
        
        if call and put:
            call_iv = call.get("implied_volatility", 0) * 100  # Convert to percentage
            put_iv = put.get("implied_volatility", 0) * 100    # Convert to percentage
            
            print(f"ATM Call: Strike ${call['details']['strike_price']:.2f}, IV: {call_iv:.1f}%")
            print(f"ATM Put:  Strike ${put['details']['strike_price']:.2f}, IV: {put_iv:.1f}%")
            print(f"IV Skew (Put - Call): {put_iv - call_iv:+.1f}%")
        else:
            print(f"Could not find ATM call/put for {exp}")

if __name__ == "__main__":
    main()
