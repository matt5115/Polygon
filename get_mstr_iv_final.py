import os
from datetime import datetime, timedelta
from polygon import RESTClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Polygon client
client = RESTClient(api_key=os.getenv('POLYGON_API_KEY'))

def get_options_chain(ticker: str, target_date: str):
    """Get options chain for a specific date"""
    try:
        # Get the stock price for the target date
        bars = list(client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=target_date,
            to=target_date
        ))
        
        if not bars:
            print(f"No price data found for {ticker} on {target_date}")
            return None
            
        current_price = bars[0].close
        print(f"{ticker} price on {target_date}: ${current_price:.2f}")
        
        # Get all options contracts
        contracts = list(client.list_options_contracts(
            underlying_ticker=ticker,
            expired=False,
            limit=1000
        ))
        
        if not contracts:
            print("No options contracts found")
            return None
            
        # Get unique expiration dates and sort them
        expirations = sorted(list(set([c.expiration_date for c in contracts])))
        print(f"\nAvailable expirations: {', '.join(expirations[:5])}{'...' if len(expirations) > 5 else ''}")
        
        # Get options data for the next 3 expirations
        options_data = []
        for exp in expirations[:3]:
            print(f"\nFetching data for {exp}...")
            
            # Get calls and puts for this expiration
            for opt_type in ['call', 'put']:
                try:
                    # Get options chain for this expiration and type
                    options = list(client.list_options_contracts(
                        underlying_ticker=ticker,
                        expiration_date=exp,
                        contract_type=opt_type,
                        limit=1000
                    ))
                    
                    # Get strikes near the money
                    strikes = sorted([o.strike_price for o in options])
                    atm_strikes = [s for s in strikes if abs(s - current_price) / current_price <= 0.05]
                    
                    for strike in atm_strikes[:5]:  # Limit to 5 strikes per side to avoid too many requests
                        try:
                            # Get the option details
                            opt = next(o for o in options if o.strike_price == strike)
                            
                            # Get the latest trade
                            trades = list(client.list_trades(
                                f"O:{opt.ticker}",
                                timestamp_gte=target_date,
                                timestamp_lte=target_date,
                                limit=1
                            ))
                            
                            if not trades:
                                continue
                                
                            # Get the latest quote
                            quotes = list(client.list_quotes(
                                f"O:{opt.ticker}",
                                timestamp_gte=target_date,
                                timestamp_lte=target_date,
                                limit=1
                            ))
                            
                            if not quotes:
                                continue
                                
                            # Get greeks if available
                            greeks = {}
                            try:
                                greeks_resp = list(client.get_daily_open_close_agg(
                                    f"O:{opt.ticker}",
                                    target_date
                                ))
                                if hasattr(greeks_resp, 'greeks'):
                                    greeks = greeks_resp.greeks
                            except:
                                pass
                            
                            options_data.append({
                                'expiration': exp,
                                'strike': strike,
                                'type': opt_type,
                                'last_trade': trades[0].price if trades else None,
                                'bid': quotes[0].bid_price if quotes else None,
                                'ask': quotes[0].ask_price if quotes else None,
                                'iv': greeks.get('implied_volatility', 0) * 100 if greeks else 0,
                                'delta': greeks.get('delta', 0) if greeks else 0,
                                'volume': sum(t.size for t in trades) if trades else 0,
                                'open_interest': opt.open_interest if hasattr(opt, 'open_interest') else 0
                            })
                            
                        except Exception as e:
                            print(f"  Error processing {opt_type} {strike}: {str(e)}")
                            continue
                            
                except Exception as e:
                    print(f"Error getting {opt_type}s for {exp}: {str(e)}")
                    continue
        
        return {
            'stock_price': current_price,
            'options': options_data
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
    
    # Filter out options with no data
    valid_options = [opt for opt in data['options'] if opt.get('last_trade') is not None]
    
    if not valid_options:
        print("No valid options data found")
        return
    
    # Sort by expiration, then type, then strike
    valid_options.sort(key=lambda x: (x['expiration'], x['type'], x['strike']))
    
    # Print results
    print(f"\n{'='*120}")
    print(f"{'Expiration':<12} | {'Type':<4} | {'Strike':<8} | {'Last':<8} | {'Bid':<8} | {'Ask':<8} | {'IV':<8} | {'Delta':<8} | {'OI':<6} | {'Volume'}")
    print(f"{'='*120}")
    
    for opt in valid_options:
        print(f"{opt['expiration']} | {opt['type'].upper():<4} | {opt['strike']:>8.2f} | "
              f"{opt['last_trade'] or 'N/A':>8.2f} | {opt['bid'] or 'N/A':>8.2f} | {opt['ask'] or 'N/A':>8.2f} | "
              f"{opt['iv']:>6.1f}% | {opt['delta']:>6.2f} | "
              f"{opt['open_interest']:>5} | {opt['volume']}")
    
    # Calculate ATM IV for calls and puts for the nearest expiration
    nearest_exp = valid_options[0]['expiration'] if valid_options else None
    if nearest_exp:
        print(f"\nAnalyzing nearest expiration: {nearest_exp}")
        
        # Get ATM options for this expiration
        exp_options = [opt for opt in valid_options if opt['expiration'] == nearest_exp]
        atm_call = next((opt for opt in exp_options if opt['type'] == 'call' and 
                        abs(opt['strike'] - data['stock_price']) <= 2.5), None)
        atm_put = next((opt for opt in exp_options if opt['type'] == 'put' and 
                       abs(opt['strike'] - data['stock_price']) <= 2.5), None)
        
        print("\nATM Implied Volatility:")
        print("-" * 40)
        if atm_call:
            print(f"ATM Call IV: {atm_call['iv']:.1f}% (Strike: {atm_call['strike']})")
        if atm_put:
            print(f"ATM Put IV:  {atm_put['iv']:.1f}% (Strike: {atm_put['strike']})")
        
        # Calculate IV skew (Put IV - Call IV)
        if atm_call and atm_put:
            iv_skew = atm_put['iv'] - atm_call['iv']
            print(f"\nIV Skew (Put IV - Call IV): {iv_skew:+.1f}%")

if __name__ == "__main__":
    main()
