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

def get_option_chain(ticker: str, date_str: str):
    """Get option chain for a ticker on a specific date"""
    try:
        # First, get the stock price on that date
        url = f"{BASE_URL}/v1/open-close/{ticker}/{date_str}"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code != 200:
            print(f"Error getting stock price: {response.text}")
            return None
            
        stock_data = response.json()
        current_price = stock_data.get('close')
        print(f"{ticker} price on {date_str}: ${current_price:.2f}")
        
        # Get options chain snapshot
        url = f"{BASE_URL}/v3/snapshot/options/{ticker}"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code != 200:
            print(f"Error getting options chain: {response.text}")
            return None
            
        return {
            'stock_price': current_price,
            'chain_data': response.json()
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def analyze_option_chain(chain_data, stock_price):
    """Analyze option chain and print ATM options"""
    if not chain_data or 'results' not in chain_data:
        print("No results in chain data")
        return
        
    # Get unique expirations
    expirations = sorted(list(set(
        result['details']['expiration_date'] 
        for result in chain_data['results']
        if 'details' in result and 'expiration_date' in result['details']
    )))
    
    print(f"\nAvailable expirations: {', '.join(expirations[:5])}{'...' if len(expirations) > 5 else ''}")
    
    # Analyze first 3 expirations
    for exp in expirations[:3]:
        print(f"\n=== Expiration: {exp} ===")
        
        # Get all options for this expiration
        exp_options = [
            opt for opt in chain_data['results']
            if opt.get('details', {}).get('expiration_date') == exp
        ]
        
        if not exp_options:
            print(f"No options found for expiration {exp}")
            continue
            
        # Find ATM options (closest strike to stock price)
        call_options = [opt for opt in exp_options if opt.get('details', {}).get('type') == 'call']
        put_options = [opt for opt in exp_options if opt.get('details', {}).get('type') == 'put']
        
        # Sort by distance from ATM
        call_options.sort(key=lambda x: abs(x.get('details', {}).get('strike_price', 0) - stock_price))
        put_options.sort(key=lambda x: abs(x.get('details', {}).get('strike_price', 0) - stock_price))
        
        # Get ATM call and put
        atm_call = call_options[0] if call_options else None
        atm_put = put_options[0] if put_options else None
        
        if atm_call and atm_put:
            call_iv = atm_call.get('implied_volatility', 0) * 100  # Convert to percentage
            put_iv = atm_put.get('implied_volatility', 0) * 100    # Convert to percentage
            
            print(f"ATM Call: Strike ${atm_call['details']['strike_price']:.2f}, IV: {call_iv:.1f}%")
            print(f"ATM Put:  Strike ${atm_put['details']['strike_price']:.2f}, IV: {put_iv:.1f}%")
            print(f"IV Skew (Put - Call): {put_iv - call_iv:+.1f}%")
        else:
            print("Could not find ATM call/put")

def main():
    # Set parameters
    ticker = "MSTR"
    target_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    print(f"Fetching option data for {ticker} on {target_date}...")
    
    # Get option chain data
    data = get_option_chain(ticker, target_date)
    if not data:
        print("Failed to fetch option data")
        return
    
    # Analyze the option chain
    analyze_option_chain(data['chain_data'], data['stock_price'])

if __name__ == "__main__":
    main()
