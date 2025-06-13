import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_historical_options(ticker: str, date: str, api_key: str):
    """Check for historical options data on a specific date."""
    # Try to get options chain for the date
    url = f"https://api.polygon.io/v3/snapshot/options/{ticker.upper()}"
    params = {
        "as_of": date,
        "apiKey": api_key
    }
    
    try:
        print(f"Fetching options snapshot for {ticker} on {date}...")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'results' in data and data['results']:
            print(f"Found {len(data['results'])} options contracts")
            print("Example contract:", data['results'][0])
        else:
            print("No options data found for this date")
            print("Response:", data)
            
    except Exception as e:
        print(f"Error fetching options data: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")

def main():
    # Get API key
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("POLYGON_API_KEY not found in environment variables")
        return
    
    ticker = "MSTR"
    target_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')  # ~May 12, 2025
    
    print(f"Checking historical options data for {ticker} on {target_date}...")
    get_historical_options(ticker, target_date, api_key)

if __name__ == "__main__":
    main()
