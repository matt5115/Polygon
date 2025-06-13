import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
BASE_URL = "https://api.polygon.io"
HEADERS = {"Authorization": f"Bearer {POLYGON_API_KEY}"}

def get_historical_iv(ticker: str, target_date: str):
    """Get historical IV for a ticker on a specific date"""
    try:
        # First, get the stock price on that date
        url = f"{BASE_URL}/v1/open-close/{ticker}/{target_date}"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code != 200:
            print(f"Error getting stock price: {response.text}")
            return None
            
        stock_data = response.json()
        current_price = stock_data.get('close')
        print(f"{ticker} price on {target_date}: ${current_price:.2f}")
        
        # Get options contracts
        url = f"{BASE_URL}/v3/reference/options/contracts"
        params = {
            "underlying_ticker": ticker,
            "as_of": target_date,
            "limit": 1000,
            "expired": "false"
        }
        
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"Error getting options contracts: {response.text}")
            return None
            
        contracts = response.json().get('results', [])
        if not contracts:
            print("No options contracts found")
            return None
            
        # Get unique expirations
        expirations = sorted(list(set(
            contract['expiration_date'] 
            for contract in contracts 
            if 'expiration_date' in contract
        )))
        
        print(f"\nAvailable expirations: {', '.join(expirations[:5])}{'...' if len(expirations) > 5 else ''}")
        
        # Get IV for the first 3 expirations
        for exp in expirations[:3]:
            print(f"\n=== {ticker} {exp} ===")
            
            # Get calls and puts for this expiration
            exp_contracts = [
                c for c in contracts 
                if c.get('expiration_date') == exp
            ]
            
            # Get ATM options (closest to current price)
            calls = [c for c in exp_contracts if c.get('contract_type') == 'call']
            puts = [c for c in exp_contracts if c.get('contract_type') == 'put']
            
            # Sort by distance from current price
            calls.sort(key=lambda x: abs(x.get('strike_price', 0) - current_price))
            puts.sort(key=lambda x: abs(x.get('strike_price', 0) - current_price))
            
            # Get ATM call and put
            atm_call = calls[0] if calls else None
            atm_put = puts[0] if puts else None
            
            if atm_call and atm_put:
                print(f"ATM Call: Strike ${atm_call.get('strike_price'):.2f}, "
                      f"IV: {atm_call.get('implied_volatility', 0) * 100:.1f}%")
                print(f"ATM Put:  Strike ${atm_put.get('strike_price'):.2f}, "
                      f"IV: {atm_put.get('implied_volatility', 0) * 100:.1f}%")
                
                iv_skew = (atm_put.get('implied_volatility', 0) - 
                          atm_call.get('implied_volatility', 0)) * 100
                print(f"IV Skew (Put - Call): {iv_skew:+.1f}%")
            else:
                print("Could not find ATM call/put")
        
        return {
            'stock_price': current_price,
            'expirations': expirations
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def main():
    # Set parameters
    ticker = "MSTR"
    target_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    print(f"Fetching historical IV for {ticker} on {target_date}...")
    
    # Get historical IV data
    get_historical_iv(ticker, target_date)

if __name__ == "__main__":
    main()
