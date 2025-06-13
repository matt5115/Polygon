import os
import sys
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variable
API_KEY = os.getenv('POLYGON_API_KEY')
if not API_KEY or API_KEY == 'your_api_key_here':
    print("Error: POLYGON_API_KEY not found in .env file")
    print("Please create a .env file with your Polygon.io API key:")
    print("POLYGON_API_KEY=your_api_key_here")
    sys.exit(1)

# Base URL for Polygon API
BASE_URL = "https://api.polygon.io"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def get_historical_options_chain(ticker: str, date_str: str):
    """
    Get options chain for a given ticker on a specific date
    """
    # First, get the stock price on that date
    url = f"{BASE_URL}/v1/open-close/{ticker}/{date_str}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code != 200:
        print(f"Error getting stock price for {ticker} on {date_str}: {response.text}")
        return None
    
    stock_data = response.json()
    current_price = stock_data.get('close')
    print(f"{ticker} price on {date_str}: ${current_price:.2f}")
    
    # Get options chain for that date
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": ticker,
        "as_of": date_str,
        "limit": 1000,  # Get as many as possible
        "expired": "false"
    }
    
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code != 200:
        print(f"Error getting options chain: {response.text}")
        return None
    
    options_data = response.json()
    return {
        'stock_price': current_price,
        'options': options_data.get('results', [])
    }

def analyze_iv(options_data):
    """
    Analyze implied volatility from options data
    """
    if not options_data or 'options' not in options_data:
        return {}
    
    atm_options = []
    for opt in options_data['options']:
        # Only look at options expiring in the next 3 months
        exp_date = datetime.strptime(opt['expiration_date'], '%Y-%m-%d')
        if (exp_date - datetime.now()).days > 90:
            continue
            
        # Calculate moneyness (how far from ATM)
        strike = opt['strike_price']
        moneyness = abs(strike - options_data['stock_price']) / options_data['stock_price']
        
        # Consider options within 5% of ATM
        if moneyness <= 0.05:
            atm_options.append({
                'expiration': opt['expiration_date'],
                'strike': strike,
                'type': opt['contract_type'],
                'iv': opt.get('implied_volatility', 0),
                'delta': opt.get('delta', 0),
                'open_interest': opt.get('open_interest', 0),
                'volume': opt.get('volume', 0)
            })
    
    return atm_options

def main():
    # Calculate date 30 days ago
    target_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    ticker = "MSTR"
    
    print(f"Fetching options data for {ticker} on {target_date}...")
    
    # Get options data
    options_data = get_historical_options_chain(ticker, target_date)
    if not options_data:
        print("Failed to fetch options data")
        return
    
    # Analyze IV
    atm_options = analyze_iv(options_data)
    
    print("\nAt-The-Money Options (within 5% of stock price):")
    print("-" * 80)
    print(f"{'Expiration':<12} | {'Type':<4} | {'Strike':<8} | {'IV':<8} | {'Delta':<8} | {'OI':<6} | {'Volume'}")
    print("-" * 80)
    
    for opt in sorted(atm_options, key=lambda x: (x['expiration'], x['type'], x['strike'])):
        print(f"{opt['expiration']} | {opt['type'].upper():<4} | {opt['strike']:>8.2f} | "
              f"{opt['iv']*100:>6.1f}% | {opt['delta']:>6.2f} | "
              f"{opt['open_interest']:>5} | {opt['volume']}")
    
    # Calculate skew (10-delta put IV - 10-delta call IV)
    # This is a simplification - in a real scenario, we'd need to interpolate to find exact 10-delta strikes
    print("\nNote: For exact 10-delta skew calculation, we'd need to interpolate between strikes")
    print("The table above shows ATM options that were available on that date.")

if __name__ == "__main__":
    main()
