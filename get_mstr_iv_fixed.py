import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# Load environment variables
load_dotenv()

# Configuration
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
BASE_URL = "https://api.polygon.io"
HEADERS = {"Authorization": f"Bearer {POLYGON_API_KEY}"}

def get_options_chain(ticker: str, date_str: str) -> Optional[Dict[str, Any]]:
    """
    Get options chain for a ticker on a specific date using the snapshot endpoint
    """
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
            
        options_data = response.json()
        
        # Process options data
        options = []
        for result in options_data.get('results', []):
            details = result.get('details', {})
            
            # Skip if missing required fields
            if not all(k in details for k in ['strike_price', 'contract_type', 'expiration_date']):
                continue
                
            # Get greeks if available
            greeks = details.get('greeks', {})
            
            options.append({
                'expiration': details['expiration_date'],
                'strike': details['strike_price'],
                'type': details['contract_type'],
                'iv': details.get('implied_volatility', 0) * 100,  # Convert to percentage
                'delta': greeks.get('delta', 0),
                'open_interest': details.get('open_interest', 0),
                'volume': details.get('volume', 0)
            })
            
        return {
            'stock_price': current_price,
            'options': options
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def main():
    # Set target date (30 days ago)
    target_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    ticker = "MSTR"
    
    print(f"Fetching options data for {ticker} on {target_date}...")
    
    # Get options data
    data = get_options_chain(ticker, target_date)
    if not data or 'options' not in data:
        print("Failed to fetch options data")
        return
    
    # Filter for ATM options (within 5% of stock price)
    atm_options = [
        opt for opt in data['options'] 
        if abs(opt['strike'] - data['stock_price']) / data['stock_price'] <= 0.05
    ]
    
    if not atm_options:
        print("No ATM options found")
        return
    
    # Sort by expiration and type
    atm_options.sort(key=lambda x: (x['expiration'], x['type'], x['strike']))
    
    # Print results
    print(f"\n{'='*100}")
    print(f"{'Expiration':<12} | {'Type':<4} | {'Strike':<8} | {'IV':<8} | {'Delta':<8} | {'OI':<6} | {'Volume'}")
    print(f"{'='*100}")
    
    for opt in atm_options:
        print(f"{opt['expiration']} | {opt['type'].upper():<4} | {opt['strike']:>8.2f} | "
              f"{opt['iv']:>6.1f}% | {opt['delta']:>6.2f} | "
              f"{opt['open_interest']:>5} | {opt['volume']}")
    
    # Calculate ATM IV for calls and puts
    atm_call = next((opt for opt in atm_options if opt['type'] == 'call' and 
                    abs(opt['strike'] - data['stock_price']) <= 2.5), None)
    atm_put = next((opt for opt in atm_options if opt['type'] == 'put' and 
                   abs(opt['strike'] - data['stock_price']) <= 2.5), None)
    
    print("\nATM Implied Volatility:")
    print("-" * 40)
    if atm_call:
        print(f"ATM Call IV: {atm_call['iv']:.1f}% (Strike: {atm_call['strike']}, Exp: {atm_call['expiration']})")
    if atm_put:
        print(f"ATM Put IV:  {atm_put['iv']:.1f}% (Strike: {atm_put['strike']}, Exp: {atm_put['expiration']}")
    
    # Calculate IV skew (Put IV - Call IV)
    if atm_call and atm_put and atm_call['expiration'] == atm_put['expiration']:
        iv_skew = atm_put['iv'] - atm_call['iv']
        print(f"\nIV Skew (Put IV - Call IV): {iv_skew:+.1f}%")

if __name__ == "__main__":
    main()
