import os
from datetime import datetime, timedelta
from polygon import RESTClient
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# Initialize Polygon client
client = RESTClient(api_key=os.getenv('POLYGON_API_KEY'))

def get_historical_iv(ticker, target_date):
    """Get historical implied volatility for a ticker on a specific date"""
    try:
        # Get the close price for the target date
        bars = client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=target_date,
            to=target_date
        )
        
        if not bars:
            print(f"No price data found for {ticker} on {target_date}")
            return None
            
        close_price = bars[0].close
        print(f"{ticker} price on {target_date}: ${close_price:.2f}")
        
        # Get options chain for that date
        options = []
        
        # Get options contracts for the next 3 months
        for opt in client.list_options_contracts(
            underlying_ticker=ticker,
            as_of=target_date,
            expired=False,
            limit=1000
        ):
            # Only include options expiring within 3 months
            exp_date = datetime.strptime(opt.expiration_date, "%Y-%m-%d").date()
            if (exp_date - target_date).days > 90:
                continue
                
            # Get option details
            try:
                details = client.get_daily_open_close_agg(
                    f"O:{opt.ticker}",
                    target_date
                )
                
                # Get option greeks if available
                greeks = getattr(details, 'greeks', {})
                
                options.append({
                    'expiration': opt.expiration_date,
                    'strike': opt.strike_price,
                    'type': opt.contract_type.lower(),
                    'iv': getattr(details, 'implied_volatility', 0) * 100,  # Convert to percentage
                    'delta': greeks.get('delta', 0) if greeks else 0,
                    'open_interest': getattr(details, 'open_interest', 0),
                    'volume': getattr(details, 'volume', 0)
                })
            except Exception as e:
                print(f"Error getting details for {opt.ticker}: {str(e)}")
                continue
                
        return {
            'stock_price': close_price,
            'options': options
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def main():
    # Calculate date 30 days ago
    target_date = (datetime.now() - timedelta(days=30)).date()
    ticker = "MSTR"
    
    print(f"Fetching options data for {ticker} on {target_date}...")
    
    # Get options data
    data = get_historical_iv(ticker, target_date)
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
    print(f"\n{'-'*100}")
    print(f"{'Expiration':<12} | {'Type':<4} | {'Strike':<8} | {'IV':<8} | {'Delta':<8} | {'OI':<6} | {'Volume'}")
    print(f"{'-'*100}")
    
    for opt in atm_options:
        print(f"{opt['expiration']} | {opt['type'].upper():<4} | {opt['strike']:>8.2f} | "
              f"{opt['iv']:>6.1f}% | {opt['delta']:>6.2f} | "
              f"{opt['open_interest']:>5} | {opt['volume']}")

if __name__ == "__main__":
    main()
