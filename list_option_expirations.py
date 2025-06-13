import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def list_option_expirations(ticker: str, api_key: str):
    """List all available option expiration dates for a ticker."""
    url = "https://api.polygon.io/v3/reference/options/contracts"
    params = {
        "underlying_ticker": ticker.upper(),
        "expired": "false",
        "limit": 1000,
        "apiKey": api_key
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Get unique expiration dates
        expirations = sorted(list(set(
            contract['expiration_date'] 
            for contract in data.get('results', []) 
            if 'expiration_date' in contract
        )))
        
        return expirations
    except Exception as e:
        print(f"Error listing option expirations: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return []

def main():
    # Get API key
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("POLYGON_API_KEY not found in environment variables")
        return
    
    ticker = "MSTR"
    print(f"Fetching option expirations for {ticker}...")
    
    expirations = list_option_expirations(ticker, api_key)
    
    if not expirations:
        print(f"No option expirations found for {ticker}")
        return
    
    print(f"\nAvailable expirations for {ticker}:")
    for i, exp in enumerate(expirations[:10], 1):  # Show first 10 expirations
        print(f"{i}. {exp}")
    
    if len(expirations) > 10:
        print(f"... and {len(expirations) - 10} more")

if __name__ == "__main__":
    main()
