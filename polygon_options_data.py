import json
import os
import requests
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple

# Configuration
# Get API key from environment variable or use placeholder
import os
API_KEY = os.environ.get('POLYGON_API_KEY', 'bDuVyIkRdkKkEfwHJJStffLPVMAgutEV')

if API_KEY == 'YOUR_API_KEY_HERE':
    print("\n⚠️  WARNING: Using placeholder API key. Please set the POLYGON_API_KEY environment variable.")
    print("You can get a free API key at https://polygon.io/")
    print("Example: export POLYGON_API_KEY='your_api_key_here'\n")

BASE_URL = "https://api.polygon.io"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# List of high-liquidity stocks with good options volume
TICKERS = [
    # Tech
    "AAPL", "TSLA", "META", "AMZN", "MSFT", "GOOGL",
    "NVDA", "AMD", "INTC", "NFLX", "SHOP", "COST",
    # Other Sectors
    "XOM", "PEP", "JNJ", "BA", "GE", "ABNB"
]  # 18 high-liquidity tickers

# Options expiration date (YYYY-MM-DD) - using June 2025 expiration
TARGET_EXPIRATION = "2025-06-20"  # Third Friday of June 2025

# Ensure we have the datetime imports we need
from datetime import datetime as dt, date as d, timedelta as td

# Options filtering parameters
MIN_STRIKE_PCT = 0.90  # 10% below current price for puts
MAX_STRIKE_PCT = 1.10  # 10% above current price for calls
MIN_DELTA = 0.10       # Minimum delta for options (wider range)
MAX_DELTA = 0.50       # Maximum delta for options (wider range)
MIN_PREMIUM = 0.10     # Lower minimum premium to see more options

# Options filtering parameters
MIN_OPEN_INTEREST = 50     # Minimum open interest to ensure liquidity
MIN_VOLUME = 0             # Allow options with any volume, rely more on OI
STRIKE_PRICE_RANGE = 0.40  # 40% range around current price

# Delta ranges for filtering
PUT_MIN_DELTA = 0.10     # Minimum delta for puts
PUT_MAX_DELTA = 0.50     # Maximum delta for puts
CALL_MIN_DELTA = 0.10    # Minimum delta for calls
CALL_MAX_DELTA = 0.90    # Maximum delta for calls (increased from 0.7)

# Premium and yield thresholds
MIN_PREMIUM = 0.10       # Minimum premium to filter out penny options
MIN_ANNUALIZED_YIELD = 10.0  # Minimum annualized yield percentage

# Output formatting
PRICE_WIDTH = 8
STRIKE_WIDTH = 10
YIELD_WIDTH = 8
DELTA_WIDTH = 8
EXPIRY_WIDTH = 12
OUTPUT_FILE = 'options_analysis.md'  # Output markdown file

def get_market_status():
    """Check if the market is currently open"""
    try:
        url = f"{BASE_URL}/v1/marketstatus/now"
        params = {'apiKey': API_KEY}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('market')
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if hasattr(e, 'response') else 'unknown'
        if status_code == 401:
            print(f"❌ Authentication failed. Please check your Polygon.io API key.")
            print(f"Current API key: {API_KEY[:4]}...{API_KEY[-4:] if len(API_KEY) > 8 else ''}")
            print("You can get a free API key at https://polygon.io/")
            print("Then set it as an environment variable: export POLYGON_API_KEY='your_api_key_here'")
            exit(1)
        print(f"Error checking market status (HTTP {status_code}): {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network error checking market status: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error checking market status: {str(e)}")
        return None

def get_stock_price(ticker):
    """
    Get the latest stock price for a given ticker.
    
    Args:
        ticker (str): Stock ticker symbol
        
    Returns:
        float: Latest stock price, or None if not available
    """
    try:
        print(f"\n{'='*60}")
        print(f"FETCHING LATEST PRICE FOR {ticker.upper()}")
        
        # Try the aggregates endpoint first (most reliable)
        url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/prev"
        params = {
            'adjusted': 'true',
            'apiKey': API_KEY
        }
        
        # Set a reasonable timeout
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if 'results' in data and data['results'] and 'c' in data['results'][0]:
            price = float(data['results'][0]['c'])
            print(f"Current price for {ticker}: ${price:.2f}")
            return price
            
        # Fallback to snapshot if aggregates doesn't work
        print("Aggregates endpoint didn't return price, trying snapshot...")
        snapshot_url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
        snapshot_params = {'apiKey': API_KEY}
        
        snapshot_response = requests.get(snapshot_url, params=snapshot_params, headers=HEADERS, timeout=15)
        snapshot_response.raise_for_status()
        snapshot_data = snapshot_response.json()
        
        # Try different possible locations of the price in the response
        price = None
        if 'ticker' in snapshot_data and 'day' in snapshot_data['ticker']:
            day_data = snapshot_data['ticker']['day']
            if 'c' in day_data:  # Closing price
                price = float(day_data['c'])
            elif 'o' in day_data:  # Opening price
                price = float(day_data['o'])
            elif 'h' in day_data and 'l' in day_data:  # Average of high and low
                price = (float(day_data['h']) + float(day_data['l'])) / 2
        
        if price is not None:
            print(f"Current price for {ticker}: ${price:.2f} (from snapshot)")
            return price
            
        print(f"❌ Could not determine current price for {ticker}")
        return None
            
    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code if hasattr(http_err, 'response') else 'Unknown'
        print(f"\n❌ HTTP {status_code} error getting price for {ticker}:")
        
        # Handle rate limiting
        if status_code == 429:
            print("Rate limit exceeded. Please wait before making more requests.")
            retry_after = http_err.response.headers.get('Retry-After', '60')
            print(f"Please wait {retry_after} seconds before trying again.")
        # Handle authentication errors
        elif status_code in [401, 403]:
            print("Authentication failed. Please check your API key.")
            print("You can get a free API key at https://polygon.io/")
            print(f"Current API key: {'*' * 8}{API_KEY[-4:] if API_KEY else 'None'}")
        
        # Print response details if available
        try:
            error_details = http_err.response.json()
            print(f"Error details: {error_details}")
        except:
            error_text = http_err.response.text[:500] if hasattr(http_err.response, 'text') else 'No details'
            print(f"Response: {error_text}")
            
    except requests.exceptions.RequestException as req_err:
        print(f"\n❌ Request error getting price for {ticker}:")
        print(f"Error: {str(req_err)}")
        
        return None
    except Exception as e:
        print(f"Unexpected error getting price for {ticker}: {str(e)}")
        return None

def get_options_chain(ticker, option_type, current_price):
    """
    Get options chain for a given ticker and option type with enhanced error handling.
    
    Args:
        ticker (str): Stock ticker symbol
        option_type (str): 'put' or 'call'
        current_price (float): Current stock price
        
    Returns:
        list: List of option contracts with details and pricing
    """
    if not API_KEY or API_KEY == 'YOUR_API_KEY_HERE':
        print("⚠️  Please set your Polygon.io API key in the environment variable POLYGON_API_KEY")
        return []
    
    print(f"\n{'='*60}")
    print(f"FETCHING {option_type.upper()} OPTIONS FOR {ticker.upper()}")
    print(f"Current Price: ${current_price:.2f}")
    
    # Calculate strike price range (wider range for calls)
    if option_type == 'put':
        min_strike = current_price * (1 - STRIKE_PRICE_RANGE)
        max_strike = current_price * (1 + STRIKE_PRICE_RANGE * 0.5)  # Tighter range for puts
    else:  # call
        min_strike = current_price * (1 - STRIKE_PRICE_RANGE * 0.5)  # Tighter range for calls
        max_strike = current_price * (1 + STRIKE_PRICE_RANGE)
    
    print(f"Fetching {option_type} options with strikes ${min_strike:.2f} to ${max_strike:.2f}...")
    
    try:
        # First, get the list of all option contracts for this ticker and expiration
        url = f"{BASE_URL}/v3/reference/options/contracts"
        params = {
            'underlying_ticker': ticker.upper(),
            'contract_type': option_type.lower(),
            'expiration_date': TARGET_EXPIRATION,
            'apiKey': API_KEY,
            'limit': 1000,  # Maximum allowed by Polygon
            'as_of': 'trades',  # Get the most recent data
            'sort': 'strike_price',
            'order': 'asc'
        }
        
        print(f"Requesting options chain from {url}...")
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if 'results' not in data or not data['results']:
            print(f"No {option_type} options found for {ticker} (exp: {TARGET_EXPIRATION})")
            return []
        print(f"Found {len(data['results'])} {option_type} contracts for {ticker}")
        return data['results']
            
    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code if hasattr(http_err, 'response') else 'Unknown'
        print(f"\n❌ HTTP {status_code} error fetching {option_type} options for {ticker}:")
        
        # Handle rate limiting
        if status_code == 429:
            print("Rate limit exceeded. Please wait before making more requests.")
            retry_after = http_err.response.headers.get('Retry-After', '60')
            print(f"Please wait {retry_after} seconds before trying again.")
        # Handle authentication errors
        elif status_code in [401, 403]:
            print("Authentication failed. Please check your API key.")
            print("You can get a free API key at https://polygon.io/")
            print(f"Current API key: {'*' * 8}{API_KEY[-4:] if API_KEY else 'None'}")
        
        # Print response details if available
        try:
            error_details = http_err.response.json()
            print(f"Error details: {error_details}")
        except:
            error_text = http_err.response.text[:500] if hasattr(http_err.response, 'text') else 'No details'
            print(f"Response: {error_text}")
            
    except requests.exceptions.RequestException as req_err:
        print(f"\n❌ Request error fetching {option_type} options for {ticker}:")
        print(f"Error: {str(req_err)}")
        
    except Exception as e:
        print(f"\n❌ Unexpected error fetching {option_type} options for {ticker}:")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return []

def get_greeks(contract):
    """Extract greeks from contract"""
    return contract.get('greeks', {})

def calculate_premium_yield(contract, current_price, is_put):
    """Calculate premium yield and other metrics for an option contract"""
    try:
        # Extract basic contract details
        details = contract.get('details', {})
        greeks = contract.get('greeks', {})
        day_data = contract.get('day', {})
        
        # Get strike price with error handling
        try:
            strike = float(details.get('strike_price', 0))
            if strike <= 0:
                print(f"Invalid strike price: {strike}")
                return None
        except (TypeError, ValueError) as e:
            print(f"Error parsing strike price: {e}")
            return None
            
        expiration = details.get('expiration_date', '')
        
        # Get pricing data - try multiple fields with error handling
        def safe_float(value, default=0.0):
            try:
                return float(value) if value is not None else default
            except (TypeError, ValueError):
                return default
                
        bid = safe_float(day_data.get('bid') or contract.get('bid'))
        ask = safe_float(day_data.get('ask') or contract.get('ask'))
        last = safe_float(day_data.get('close') or day_data.get('last'))
        open_price = safe_float(day_data.get('open'))
        if bid > 0 and ask > 0:
            mid_price = (bid + ask) / 2
        elif last > 0:
            mid_price = last
            # If only one of bid/ask is available, use it to improve mid
            if bid > 0:
                mid_price = (bid + last) / 2
            elif ask > 0:
                mid_price = (ask + last) / 2
        else:
            mid_price = max(bid, ask, last)  # Best available price
        
        # Skip if we can't determine a valid price
        if mid_price <= 0:
            return {}
        
        # Calculate days to expiration
        dte = 0
        if expiration_date:
            try:
                exp_date = datetime.strptime(expiration_date, '%Y-%m-%d').date()
                dte = (exp_date - date.today()).days
                dte = max(1, dte)  # Ensure at least 1 day to expiration
            except (ValueError, TypeError):
                dte = 30  # Default to 30 days if can't parse date
        else:
            dte = 30  # Default to 30 days if no expiration date
        
        # Get Greeks with defaults
        delta = float(contract.get('delta', 0) or 0)
        gamma = float(contract.get('gamma', 0) or 0)
        theta = float(contract.get('theta', 0) or 0)
        vega = float(contract.get('vega', 0) or 0)
        implied_vol = float(contract.get('implied_volatility', 0) or 0) * 100  # Convert to percentage
        
        # Calculate moneyness (distance from current price as a percentage)
        if current_price > 0:
            if is_put:
                moneyness = (strike_price - current_price) / current_price
            else:
                moneyness = (current_price - strike_price) / current_price
        else:
            moneyness = 0
        
        # Calculate premium yield (premium / strike price for puts, premium / current price for calls)
        if is_put:
            premium_yield = (mid_price / strike_price * 100) if strike_price > 0 else 0
        else:
            premium_yield = (mid_price / current_price * 100) if current_price > 0 else 0
        
        # Annualize the yield (simple method)
        annualized_yield = premium_yield * (365 / dte) if dte > 0 else 0
        
        # Calculate return on capital
        # For puts: premium / strike_price (cash needed to secure the put)
        # For calls: premium / current_price (cash needed to buy 100 shares)
        if is_put:
            return_on_capital = (mid_price / strike_price * 100) if strike_price > 0 else 0
        else:
            return_on_capital = (mid_price / current_price * 100) if current_price > 0 else 0
        
        # Calculate break-even price
        if is_put:
            break_even = strike_price - mid_price
            intrinsic_value = max(0, strike_price - current_price)
        else:
            break_even = strike_price + mid_price
            intrinsic_value = max(0, current_price - strike_price)
        
        # Calculate time value and % of premium that's time value
        time_value = max(0, mid_price - intrinsic_value)
        time_value_pct = (time_value / mid_price * 100) if mid_price > 0 else 0
        
        # Estimate probability in the money (using delta as a rough estimate)
        # Note: This is an approximation and not a true probability
        probability_itm = abs(delta) * 100  # Convert to percentage
        
        # Calculate premium per day (theta equivalent)
        premium_per_day = mid_price / dte if dte > 0 else 0
        
        # Calculate risk/reward ratio (simplified)
        if is_put:
            max_risk = strike_price - mid_price
            max_reward = mid_price
        else:
            max_risk = float('inf')  # Unlimited risk for naked calls
            max_reward = mid_price
        
        risk_reward_ratio = (max_reward / max_risk) if max_risk > 0 else float('inf')
        
        # Calculate bid-ask spread and spread as % of mid
        spread = ask - bid if bid > 0 and ask > 0 else 0
        spread_pct = (spread / mid_price * 100) if mid_price > 0 else 0
        
        return {
            # Core contract details
            'strike_price': strike_price,
            'expiration_date': expiration_date,
            'days_to_expiration': dte,
            
            # Pricing
            'bid': bid,
            'ask': ask,
            'last': last,
            'mid_price': mid_price,
            'intrinsic_value': intrinsic_value,
            'time_value': time_value,
            'time_value_pct': time_value_pct,
            'bid_ask_spread': spread,
            'spread_pct': spread_pct,
            
            # Greeks
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'implied_volatility': implied_vol,
            
            # Yield metrics
            'premium_yield': premium_yield,
            'annualized_yield': annualized_yield,
            'return_on_capital': return_on_capital,
            'premium_per_day': premium_per_day,
            
            # Risk metrics
            'break_even': break_even,
            'probability_itm': probability_itm,
            'risk_reward_ratio': risk_reward_ratio,
            'moneyness': moneyness,
            'itm': intrinsic_value > 0,
            
            # Volume and open interest
            'open_interest': int(contract.get('open_interest', 0) or 0),
            'volume': int(contract.get('volume', 0) or 0),
            'volume_oi_ratio': (int(contract.get('volume', 0) or 0) / 
                              int(contract.get('open_interest', 1) or 1)) if contract.get('open_interest') else 0
        }
        
    except Exception as e:
        print(f"Error calculating option metrics: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def summarize_options(options, current_price, is_put=True):
    """
    Process and summarize options data with enhanced metrics and filtering.
    
    Args:
        options (list): List of option contracts from Polygon API
        current_price (float): Current stock price
        is_put (bool, optional): Whether these are put options. Defaults to True.
        
    Returns:
        list: List of processed option dictionaries with comprehensive metrics
    """
    if not options:
        print("No options provided for summarization")
        return []
    
    print(f"\n{'='*60}")
    print(f"SUMMARIZING {'PUT' if is_put else 'CALL'} OPTIONS (Current Price: ${current_price:.2f})")
    print(f"Processing {len(options)} options...")
    print("-"*60)
    
    processed_options = []
    skipped_count = 0
    
    for i, contract in enumerate(options):
        try:
            # Skip if no pricing data
            if not contract.get('last_quote'):
                skipped_count += 1
                continue
            
            # Get strike price and expiration
            strike = contract.get('strike_price')
            expiration = contract.get('expiration_date')
            
            # Calculate days to expiration
            if expiration:
                try:
                    expiration_date = datetime.strptime(expiration, '%Y-%m-%d').date()
                    dte = (expiration_date - date.today()).days
                    if dte <= 0:  # Skip expired options
                        skipped_count += 1
                        continue
                except (ValueError, TypeError):
                    dte = 0
            else:
                dte = 0
            
            # Get bid/ask/last prices with fallbacks
            last_quote = contract.get('last_quote', {})
            bid = float(last_quote.get('bid', 0) or 0)
            ask = float(last_quote.get('ask', 0) or 0)
            last = float(last_quote.get('last', 0) or 0)
            
            # Calculate mid price with better fallback logic
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2
            elif last > 0:
                mid = last
                # If only one of bid/ask is available, use it to improve mid
                if bid > 0:
                    mid = (bid + last) / 2
                elif ask > 0:
                    mid = (ask + last) / 2
            else:
                mid = max(bid, ask, last)
            
            # Skip if we can't determine a valid price
            if mid <= 0:
                skipped_count += 1
                continue
                
            # Calculate delta (absolute value for puts)
            delta = abs(float(contract.get('delta', 0) or 0))
            
            # Calculate premium yield and other metrics
            metrics = calculate_premium_yield(contract, current_price, is_put)
            
            # Get open interest and volume with defaults
            open_interest = int(contract.get('open_interest', 0) or 0)
            volume = int(contract.get('volume', 0) or 0)
            
            # Get implied volatility (convert to percentage)
            iv = float(contract.get('implied_volatility', 0) or 0) * 100
            
            # Calculate moneyness and ITM status
            if is_put:
                moneyness = (strike - current_price) / current_price
                itm = strike > current_price
            else:
                moneyness = (current_price - strike) / current_price
                itm = strike < current_price
            
            # Create option dictionary with all metrics
            option_data = {
                'contract_symbol': contract.get('ticker', '').strip(),
                'strike_price': float(strike or 0),
                'expiration_date': expiration or '',
                'dte': dte,
                'bid': bid,
                'ask': ask,
                'last': last,
                'mid_price': mid,
                'delta': delta,
                'open_interest': open_interest,
                'volume': volume,
                'implied_volatility': iv,
                'premium_yield': metrics.get('premium_yield', 0),
                'annualized_yield': metrics.get('annualized_yield', 0),
                'return_on_capital': metrics.get('return_on_capital', 0),
                'break_even': metrics.get('break_even', 0),
                'probability_itm': metrics.get('probability_itm', 0),
                'moneyness': moneyness,
                'itm': itm,
                'bid_ask_spread': ask - bid if bid > 0 and ask > 0 else 0,
                'spread_percent': ((ask - bid) / mid * 100) if bid > 0 and ask > 0 and mid > 0 else 0
            }
            
            processed_options.append(option_data)
            
            # Print progress for large datasets
            if (i + 1) % 50 == 0:
                print(f"Processed {i+1} options...")
            
        except Exception as e:
            print(f"Error processing option {i+1}: {str(e)}")
            continue
    
    print(f"\nProcessed {len(processed_options)} options (skipped {skipped_count} invalid/expired)")
    
    if not processed_options:
        print("No valid options found after processing")
        return []
    
    # Filter and sort the options
    return filter_and_sort_options(processed_options, current_price, is_put)

def filter_and_sort_options(options, current_price, is_put=True):
    """
    Filter and sort options based on criteria with improved filtering and fallback logic.
    
    Args:
        options (list): List of option dictionaries with metrics
        current_price (float): Current stock price
        is_put (bool, optional): Whether these are put options. Defaults to True.
        
    Returns:
        list: Filtered and sorted list of option dictionaries with additional metrics
    """
    if not options:
        return []
    
    # Adjust delta ranges and strike range based on option type
    if is_put:
        min_delta = PUT_MIN_DELTA
        max_delta = PUT_MAX_DELTA
        strike_range = STRIKE_PRICE_RANGE
    else:
        min_delta = CALL_MIN_DELTA
        max_delta = CALL_MAX_DELTA
        strike_range = STRIKE_PRICE_RANGE * 1.2  # Slightly wider strike range for calls
    
    print(f"\n{'='*60}")
    print(f"FILTERING {'PUT' if is_put else 'CALL'} OPTIONS (Current Price: ${current_price:.2f})")
    print(f"Delta Range: {min_delta} to {max_delta}")
    print(f"Strike Price Range: ${current_price * (1 - strike_range):.2f} to ${current_price * (1 + strike_range):.2f}")
    print(f"Minimum Premium: ${MIN_PREMIUM}")
    print(f"Minimum Open Interest: {MIN_OPEN_INTEREST}")
    print(f"Minimum Volume: {MIN_VOLUME}")
    print(f"Minimum Annualized Yield: {MIN_ANNUALIZED_YIELD}%")
    print("-"*60)
    
    filtered_options = []
    
    for i, option in enumerate(options[:100]):  # Check more options to find good candidates
        skip_reason = None
        
        try:
            # Calculate moneyness
            if is_put:
                moneyness = (option['strike_price'] - current_price) / current_price
                itm = option['strike_price'] > current_price
            else:
                moneyness = (current_price - option['strike_price']) / current_price
                itm = option['strike_price'] < current_price
            
            # Calculate metrics
            premium = option.get('mid_price', 0)
            annualized_yield = option.get('annualized_yield', 0)
            delta = abs(option.get('delta', 0))
            
            # Check all filter conditions
            if not all(k in option for k in ['strike_price', 'delta', 'premium_yield']):
                skip_reason = "Missing required fields"
            elif not (min_delta <= delta <= max_delta):
                skip_reason = f"Delta {delta:.4f} outside range [{min_delta}, {max_delta}]"
            elif premium < MIN_PREMIUM:
                skip_reason = f"Premium ${premium:.2f} below minimum ${MIN_PREMIUM}"
            elif option.get('open_interest', 0) < MIN_OPEN_INTEREST:
                skip_reason = f"Open interest {option.get('open_interest', 0)} below minimum {MIN_OPEN_INTEREST}"
            elif annualized_yield < MIN_ANNUALIZED_YIELD:
                skip_reason = f"Annualized yield {annualized_yield:.1f}% below minimum {MIN_ANNUALIZED_YIELD}%"
            
            # Only show detailed logs for the first 20 options to reduce noise
            if i < 20 or skip_reason is None:
                print(f"\n--- Option {i+1} ---")
                print(f"Contract: {option.get('contract_symbol', 'N/A')}")
                print(f"Strike: ${option.get('strike_price', 'N/A'):.2f} (${current_price - option.get('strike_price', 0):.2f} {'ITM' if itm else 'OTM'})")
                print(f"Exp: {option.get('expiration_date', 'N/A')} | DTE: {option.get('dte', 'N/A')}")
                print(f"Δ: {delta:.4f} | Premium: ${premium:.2f} | Yield: {option.get('premium_yield', 0):.2f}%")
                print(f"OI: {option.get('open_interest', 0):,} | Vol: {option.get('volume', 0):,} | IV: {option.get('implied_volatility', 0):.1f}%")
                print(f"Bid: ${option.get('bid', 0):.2f} | Ask: ${option.get('ask', 0):.2f} | Last: ${option.get('last', 0):.2f}")
                print(f"Annualized: {annualized_yield:.1f}% | ROC: {option.get('return_on_capital', 0):.1f}%")
                
                if skip_reason:
                    print(f"❌ Skipping - {skip_reason}")
            
            if not skip_reason:
                # Add additional metrics to the option
                option['moneyness'] = moneyness
                option['itm'] = itm
                option['days_to_exp'] = (datetime.strptime(option.get('expiration_date', ''), '%Y-%m-%d').date() - date.today()).days
                filtered_options.append(option)
                
        except Exception as e:
            print(f"Error processing option {i+1}: {str(e)}")
            continue
            print(f"❌ Skipping - Open interest {option['open_interest']} below minimum {MIN_OPEN_INTEREST}")
            continue
            
        if 'volume' in option and option['volume'] < MIN_VOLUME:
            print(f"❌ Skipping - Volume {option['volume']} below minimum {MIN_VOLUME}")
            continue
            
        # Check days to expiration
        if 'days_to_exp' in option and option['days_to_exp'] < 7:
            print(f"⚠️  Warning - Only {option['days_to_exp']} days to expiration")
            
        # Calculate and display key metrics
        premium_yield = (option['mid'] / current_price) * 100
        annualized = option.get('annualized_return', 0)
        roc = option.get('return_on_capital', 0)
        print(f"✅ Passing all filters - Yield: {premium_yield:.2f}%, Annualized: {annualized:.2f}%, ROC: {roc:.2f}%")
        
        filtered_options.append(option)
    
    # Sort by annualized return (descending)
    filtered_options.sort(key=lambda x: x.get('annualized_return', 0), reverse=True)
    
    print(f"\nFound {len(filtered_options)} options that passed all filters")
    return filtered_options

def format_option_display(options, is_put=True):
    """Format options for display"""
    if not options:
        return ""
        
    # Define column widths
    STRIKE_WIDTH = 10
    PRICE_WIDTH = 12
    DELTA_WIDTH = 6
    YIELD_WIDTH = 8
    EXPIRY_WIDTH = 10
    
    # Header
    header = (f"{'Strike':<{STRIKE_WIDTH}} | "
              f"{'Bid/Ask':<{PRICE_WIDTH}} | "
              f"{'Mid':<{PRICE_WIDTH}} | "
              f"{'Δ':<{DELTA_WIDTH}} | "
              f"{'Yield %':<{YIELD_WIDTH}} | "
              f"{'Ann. %':<{YIELD_WIDTH}} | "
              f"{'Expires':<{EXPIRY_WIDTH}}")
    
    separator = '-' * len(header)
    
    # Format each option
    lines = [header, separator]
    for opt in options[:5]:  # Show top 5
        strike = f"${opt['strike']:.2f}"
        bid_ask = f"{opt.get('bid', 0):.2f}/{opt.get('ask', 0):.2f}"
        mid = f"{opt.get('mid', 0):.2f}"
        delta = f"{opt.get('delta', 0):.2f}"
        yield_pct = f"{opt.get('premium_yield', 0):.2f}%"
        annualized = f"{opt.get('annualized_return', 0):.1f}%"
        exp_date = opt.get('expiration', 'N/A')
        
        line = (f"{strike:<{STRIKE_WIDTH}} | "
               f"{bid_ask:<{PRICE_WIDTH}} | "
               f"{mid:<{PRICE_WIDTH}} | "
               f"{delta:<{DELTA_WIDTH}} | "
               f"{yield_pct:<{YIELD_WIDTH}} | "
               f"{annualized:<{YIELD_WIDTH}} | "
               f"{exp_date}")
        lines.append(line)
    
    return '\n'.join(lines)

def save_to_markdown(ticker, price, puts=None, calls=None, filename=None):
    """
    Save options analysis to a markdown file.
    
    Args:
        ticker (str): Stock ticker symbol
        price (float): Current stock price
        puts (list, optional): List of put option dictionaries
        calls (list, optional): List of call option dictionaries
        filename (str, optional): Output filename. If None, uses a default name.
    """
    if puts is None:
        puts = []
    if calls is None:
        calls = []
        
    # Create output directory if it doesn't exist
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    
    # If no filename provided, use a default one with timestamp
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/options_analysis_{ticker}_{timestamp}.md"
    
    # Prepare markdown content
    md_content = [
        f"# 📊 Options Analysis - {ticker}",
        f"**Date/Time:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Current Price:** ${price:.2f}",
        ""
    ]
    
    # Add puts section if available
    if puts:
        md_content.extend([
            "## 📉 Cash-Secured Puts",
            "| Contract | Strike | Premium | Δ | Yield | Annualized | ROC | DTE | OI | Vol |",
            "|----------|--------|---------|--|-------|------------|-----|-----|----|-----|"
        ])
        for put in sorted(puts, key=lambda x: x['strike'], reverse=True):
            md_content.append(
                f"| {put.get('symbol', 'N/A')} | ${put['strike']:.2f} | ${put['mid']:.2f} | "
                f"{put.get('delta', 0):+.2f} | {put['premium_yield']:.2f}% | {put['annualized_return']:.2f}% | "
                f"{put['roc']:.2f}% | {put.get('dte', 0)}d | {put.get('open_interest', 0)} | {put.get('volume', 0)} |"
            )
    else:
        md_content.append("No put options available.")
    
    # Add calls section if available
    if calls:
        md_content.extend([
            "\n## 📈 Covered Calls",
            "| Contract | Strike | Premium | Δ | Yield | Annualized | ROC | DTE | OI | Vol |",
            "|----------|--------|---------|--|-------|------------|-----|-----|----|-----|"
        ])
        for call in sorted(calls, key=lambda x: x['strike']):
            md_content.append(
                f"| {call.get('symbol', 'N/A')} | ${call['strike']:.2f} | ${call['mid']:.2f} | "
                f"{call.get('delta', 0):+.2f} | {call['premium_yield']:.2f}% | {call['annualized_return']:.2f}% | "
                f"{call['roc']:.2f}% | {call.get('dte', 0)}d | {call.get('open_interest', 0)} | {call.get('volume', 0)} |"
            )
    else:
        md_content.append("\nNo call options available.")
    
    # Write to file
    with open(filename, 'a', encoding='utf-8') as f:
        f.write('\n'.join(md_content) + '\n\n')
    
    return filename

def print_header():
    """Print analysis header with market status"""
    print("\n" + "="*80)
    print(f"📊 OPTIONS SCREENER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*80)
    
    # Check market status
    market_status = get_market_status()
    if market_status == 'open':
        status_msg = "✅ Market is currently OPEN"
    elif market_status == 'closed':
        status_msg = "❌ Market is currently CLOSED (data may be stale)"
    else:
        status_msg = "ℹ️ Market status unknown"
    
    print(f"\n{status_msg}")
    print("-"*80)
    
    # Prepare markdown content
    md_content = [
        f"# 📊 Options Screener - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 📈 Market Status",
        f"- **Current time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- {status_msg}",
        "",
        "## 🔍 Analysis Parameters",
        f"- **Tickers analyzed:** {len(TICKERS)}",
        f"- **Option type:** Cash-secured puts & covered calls",
        f"- **Expiration target:** {TARGET_EXPIRATION}",
        f"- **Delta range:** {MIN_DELTA:.2f} to {MAX_DELTA:.2f}",
        f"- **Minimum premium:** ${MIN_PREMIUM:.2f}",
        f"- **Minimum open interest:** {MIN_OPEN_INTEREST}",
        f"- **Minimum volume:** {MIN_VOLUME}",
        ""
    ]
    
    return md_content

def run():
    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)
    
    # Get current timestamp for the output file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'output/options_analysis_{timestamp}.md'
    
    # Print header and get initial markdown content
    md_content = print_header()
    
    # Initialize results storage
    all_puts = []
    all_calls = []
    stats = {
        'tickers_processed': 0,
        'tickers_with_puts': 0,
        'tickers_with_calls': 0,
        'total_puts_found': 0,
        'total_calls_found': 0,
        'start_time': datetime.now(),
        'errors': []
    }
    
    # Process each ticker
    for ticker in TICKERS:
        try:
            stats['tickers_processed'] += 1
            print(f"\n{'='*80}\n📊 [{stats['tickers_processed']}/{len(TICKERS)}] Analyzing {ticker}")
            print("-"*80)
            
            # Get stock price
            price = get_stock_price(ticker)
            if not price:
                error_msg = f"❌ Failed to fetch price for {ticker}"
                print(error_msg)
                stats['errors'].append(error_msg)
                continue
                
            print(f"💵 Current Price: ${price:.2f}")
            
            # Get options chains
            print("\n🔍 Fetching options data...")
            puts = get_options_chain(ticker, 'put', price)
            calls = get_options_chain(ticker, 'call', price)
            
            # Summarize options
            print("\n📊 Analyzing PUT options...")
            put_results = summarize_options(puts, price, is_put=True)
            print("\n📊 Analyzing CALL options...")
            call_results = summarize_options(calls, price, is_put=False)
            
            # Store results for summary
            if put_results:
                stats['tickers_with_puts'] += 1
                stats['total_puts_found'] += len(put_results)
                for put in put_results:
                    all_puts.append({
                        'ticker': ticker,
                        'price': price,
                        **put
                    })
                
            if call_results:
                stats['tickers_with_calls'] += 1
                stats['total_calls_found'] += len(call_results)
                for call in call_results:
                    all_calls.append({
                        'ticker': ticker,
                        'price': price,
                        **call
                    })
            
            # Add ticker results to markdown
            md_content.append(f"## {ticker} - ${price:.2f}")
            
            # Add PUT results
            if put_results:
                md_content.extend([
                    "### 📉 Cash-Secured Puts (Best Yields)",
                    "| Contract | Strike | Premium | Δ | Yield | Annualized | ROC | DTE | OI | Vol |",
                    "|----------|--------|---------|--|-------|------------|-----|-----|----|-----|"
                ])
                
                for put in put_results[:5]:  # Top 5 puts
                    md_content.append(
                        f"| {put['symbol']} | ${put['strike']:.2f} | ${put['mid']:.2f} | "
                        f"{put['delta']:+.2f} | {put['premium_yield']:.2f}% | {put['annualized_return']:.2f}% | "
                        f"{put['roc']:.2f}% | {put['dte']}d | {put['open_interest']} | {put['volume']} |"
                    )
                
                # Save puts to markdown
                save_to_markdown(ticker, price, put_results, [], filename=output_file)
            else:
                md_content.append("No suitable put options found matching criteria.")
            
            # Add CALL results
            if call_results:
                md_content.extend([
                    "\n### 📈 Covered Calls (Best Yields)",
                    "| Contract | Strike | Premium | Δ | Yield | Annualized | ROC | DTE | OI | Vol |",
                    "|----------|--------|---------|--|-------|------------|-----|-----|----|-----|"
                ])
                
                for call in call_results[:5]:  # Top 5 calls
                    md_content.append(
                        f"| {call['symbol']} | ${call['strike']:.2f} | ${call['mid']:.2f} | "
                        f"{call['delta']:+.2f} | {call['premium_yield']:.2f}% | {call['annualized_return']:.2f}% | "
                        f"{call['roc']:.2f}% | {call['dte']}d | {call['open_interest']} | {call['volume']} |"
                    )
                
                # Save calls to markdown
                save_to_markdown(ticker, price, [], call_results, filename=output_file)
            else:
                md_content.append("\nNo suitable call options found matching criteria.")
            
            md_content.append("\n---\n")
            
        except Exception as e:
            error_msg = f"❌ Error processing {ticker}: {str(e)}"
            print(error_msg)
            stats['errors'].append(error_msg)
            import traceback
            traceback.print_exc()
    
    # Add summary section
    stats['end_time'] = datetime.now()
    stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds() / 60
    
    md_content.extend([
        "## 📊 Summary",
        "### Scan Statistics",
        f"- **Tickers Processed:** {stats['tickers_processed']}",
        f"- **Tickers with Valid Puts:** {stats['tickers_with_puts']}",
        f"- **Tickers with Valid Calls:** {stats['tickers_with_calls']}",
        f"- **Total Puts Found:** {stats['total_puts_found']}",
        f"- **Total Calls Found:** {stats['total_calls_found']}",
        f"- **Total Time:** {stats['duration']:.1f} minutes",
        "",
        "### 🏆 Top Opportunities"
    ])
    
    # Add top puts and calls
    if all_puts:
        top_puts = sorted(all_puts, key=lambda x: x['annualized_return'], reverse=True)[:5]
        md_content.extend([
            "#### 💰 Top 5 Cash-Secured Puts",
            "| Ticker | Price | Strike | Premium | Δ | Yield | Annualized | ROC | DTE |",
            "|--------|-------|--------|---------|--|-------|------------|-----|-----|"
        ])
        for put in top_puts:
            md_content.append(
                f"| {put['ticker']} | ${put['price']:.2f} | ${put['strike']:.2f} | ${put['mid']:.2f} | "
                f"{put['delta']:+.2f} | {put['premium_yield']:.2f}% | {put['annualized_return']:.2f}% | "
                f"{put['roc']:.2f}% | {put['dte']}d |"
            )
    
    if all_calls:
        top_calls = sorted(all_calls, key=lambda x: x['annualized_return'], reverse=True)[:5]
        md_content.extend([
            "\n#### 💰 Top 5 Covered Calls",
            "| Ticker | Price | Strike | Premium | Δ | Yield | Annualized | ROC | DTE |",
            "|--------|-------|--------|---------|--|-------|------------|-----|-----|"
        ])
        for call in top_calls:
            md_content.append(
                f"| {call['ticker']} | ${call['price']:.2f} | ${call['strike']:.2f} | ${call['mid']:.2f} | "
                f"{call['delta']:+.2f} | {call['premium_yield']:.2f}% | {call['annualized_return']:.2f}% | "
                f"{call['roc']:.2f}% | {call['dte']}d |"
            )
    
    # Add any errors to the end of the report
    if stats['errors']:
        md_content.extend([
            "",
            "## ⚠️ Errors Encountered",
            "The following errors occurred during processing:"
        ])
        for error in stats['errors']:
            md_content.append(f"- {error}")
    
    # Write the final markdown file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_content))
    
    print(f"\n{'='*80}\n✅ Analysis complete!")
    print(f"📄 Report saved to: {os.path.abspath(output_file)}")
    print("="*80)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrupted by user")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
