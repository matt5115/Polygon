import json
import os
import random
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union, Tuple
from trade_simulator import simulate_recommended_trades
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
MIN_PREMIUM = 0.50     # Minimum premium per contract in $

# Yield & Premium
MIN_ANNUALIZED_YIELD = 20.0  # Minimum annualized yield in %
MIN_ROC = 2.0  # Minimum return on capital in % per month

# Probability & Risk
MIN_PROBABILITY_ITM = 65.0  # Minimum probability ITM in %
MAX_BID_ASK_SPREAD_PCT = 10.0  # Maximum bid-ask spread as % of mid price

# Greeks Filtering
PUT_MIN_DELTA = 0.20  # 20 delta puts
PUT_MAX_DELTA = 0.35  # 35 delta puts
CALL_MIN_DELTA = 0.20  # 20 delta calls
CALL_MAX_DELTA = 0.35  # 35 delta calls

# Volume and Open Interest
MIN_OPEN_INTEREST = 100  # Minimum open interest
MIN_VOLUME = 50  # Minimum daily volume

# Output formatting
PRICE_WIDTH = 8
STRIKE_WIDTH = 10
YIELD_WIDTH = 8
DELTA_WIDTH = 8
EXPIRY_WIDTH = 12
OUTPUT_FILE = 'options_analysis.md'  # Output markdown file

# Strike price range for options chain (as a percentage of current price)
STRIKE_PRICE_RANGE = 0.30  # 30% range around current price

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

def get_options_chain(ticker, option_type, current_price, max_retries=5, initial_delay=2):
    """
    Get options chain for a given ticker and option type with enhanced error handling and retries.
    
    Args:
        ticker (str): Stock ticker symbol
        option_type (str): 'put' or 'call'
        current_price (float): Current stock price
        max_retries (int): Maximum number of retry attempts
        initial_delay (int): Initial delay between retries in seconds
        
    Returns:
        list: List of option contracts with details and pricing, or empty list on failure
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
    
    # Prepare request parameters
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
    
    # Implement retry logic with exponential backoff
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                # Calculate exponential backoff delay with jitter
                delay = min(initial_delay * (2 ** (attempt - 1)) + (random.uniform(0, 1)), 30)  # Cap at 30 seconds
                print(f"⏳ Retry attempt {attempt}/{max_retries} in {delay:.1f} seconds...")
                time.sleep(delay)
            
            # Print detailed request info for debugging
            print(f"\n🔍 Request #{attempt + 1} for {ticker} {option_type.upper()} options:")
            print(f"   URL: {url}")
            print(f"   Params: { {k: v for k, v in params.items() if k != 'apiKey'} }")
            
            start_time = time.time()
            response = requests.get(url, params=params, headers=HEADERS, timeout=15)
            response_time = time.time() - start_time
            
            print(f"✅ Response received in {response_time:.2f}s (Status: {response.status_code})")
            
            # Check for rate limiting headers
            if 'X-RateLimit-Requests-Remaining' in response.headers:
                remaining = response.headers['X-RateLimit-Requests-Remaining']
                limit = response.headers.get('X-RateLimit-Requests-Limit', 'unknown')
                print(f"   Rate limit: {remaining}/{limit} requests remaining")
            
            response.raise_for_status()
            
            data = response.json()
            
            # Check if we got a valid response
            if 'status' in data and data['status'] == 'ERROR':
                error_msg = data.get('error', 'Unknown error from Polygon API')
                print(f"❌ API Error: {error_msg}")
                if attempt == max_retries:
                    return []
                continue
            
            if 'results' not in data:
                print(f"❌ Unexpected response format from API: {data}")
                if attempt == max_retries:
                    return []
                continue
                
            if not data['results']:
                print(f"ℹ️  No {option_type} options found for {ticker} (exp: {TARGET_EXPIRATION})")
                return []
                
            print(f"✅ Found {len(data['results'])} {option_type} contracts for {ticker}")
            return data['results']
            
        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code if hasattr(http_err, 'response') else 'Unknown'
            
            # Log detailed error information
            print(f"\n❌ HTTP {status_code} Error:")
            try:
                error_details = http_err.response.json()
                print(f"   Error Details: {error_details}")
            except:
                error_text = http_err.response.text[:500] if hasattr(http_err.response, 'text') else 'No details'
                print(f"   Response: {error_text}")
            
            # Don't retry on client errors (4xx) except 429 (rate limit) and 502/503/504 (temporary server errors)
            if 400 <= status_code < 500 and status_code not in [429, 502, 503, 504]:
                if status_code in [401, 403]:
                    print("❌ Authentication failed. Please check your API key.")
                    print("   You can get a free API key at https://polygon.io/")
                    print(f"   Current API key: {'*' * len(API_KEY) if API_KEY else 'None'}")
                return []
                
            # If we've reached max retries, give up
            if attempt == max_retries:
                print(f"\n❌ Max retries ({max_retries}) reached for {option_type} options on {ticker}")
                if status_code == 429:
                    retry_after = http_err.response.headers.get('Retry-After', 'unknown')
                    print(f"   Rate limit exceeded. Please wait {retry_after} seconds before trying again.")
                return []
                
            print(f"\n⚠️  Attempt {attempt + 1} failed with HTTP {status_code}, retrying...")
            
        except requests.exceptions.RequestException as req_err:
            if attempt == max_retries:
                print(f"\n❌ Max retries reached for {option_type} options on {ticker}")
                print(f"   Request error: {req_err}")
                return []
            print(f"\n⚠️  Request error (attempt {attempt + 1}): {req_err}, retrying...")
            
        except json.JSONDecodeError as json_err:
            print(f"❌ Failed to parse JSON response: {json_err}")
            if attempt == max_retries:
                return []
                
        except Exception as e:
            if attempt == max_retries:
                print(f"\n❌ Max retries reached for {option_type} options on {ticker}")
                print(f"   Unexpected error: {e}")
                import traceback
                traceback.print_exc()
                return []
            print(f"\n⚠️  Unexpected error (attempt {attempt + 1}): {e}, retrying...")
    
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
    
    # Filter and sort the options
    return filter_and_sort_options(processed_options, current_price, is_put)

def filter_and_sort_options(options: List[Dict], current_price: float, is_put: bool = True) -> List[Dict]:
    """
    Filter and sort options based on advanced criteria and rank them for potential trades.
    
    Args:
        options: List of option dictionaries with pricing and greeks
        current_price: Current price of the underlying asset
        is_put: Whether these are put options (True) or call options (False)
        
    Returns:
        List of filtered and ranked option dictionaries with additional metrics
    """
    if not options:
        print("No options provided for filtering.")
        return []
    
    filtered = []
    
    # Set parameters based on option type
    min_delta = PUT_MIN_DELTA if is_put else CALL_MIN_DELTA
    max_delta = PUT_MAX_DELTA if is_put else CALL_MAX_DELTA
    option_type = 'Put' if is_put else 'Call'
    
    print(f"\n🔍 Filtering {option_type} options (Δ {min_delta}-{max_delta}):")
    
    for opt in options:
        try:
            # Skip if missing required fields
            required_fields = ['strike_price', 'delta', 'mid_price', 'days_to_expiration',
                             'bid', 'ask', 'open_interest', 'volume']
            if not all(k in opt for k in required_fields):
                continue
            
            strike = opt['strike_price']
            delta = abs(opt['delta'])  # Use absolute value for puts
            
            # Skip if delta is outside our target range
            if not (min_delta <= delta <= max_delta):
                continue
            
            # Skip if strike is too far from current price
            strike_pct = (strike / current_price - 1) * 100
            if is_put and strike_pct > (STRIKE_PRICE_RANGE * 100):
                continue
            elif not is_put and strike_pct < -(STRIKE_PRICE_RANGE * 100):
                continue
            
            # Skip if open interest or volume is too low
            if opt['open_interest'] < MIN_OPEN_INTEREST:
                continue
                
            if opt['volume'] < MIN_VOLUME:
                continue
            
            # Calculate bid-ask spread as % of mid price
            spread = opt['ask'] - opt['bid']
            spread_pct = (spread / opt['mid_price'] * 100) if opt['mid_price'] > 0 else 100
            
            # Skip if spread is too wide
            if spread_pct > MAX_BID_ASK_SPREAD_PCT:
                continue
            
            # Calculate days to expiration
            dte = max(1, opt.get('days_to_expiration', 30))
            
            # Calculate premium per day
            premium_per_day = opt['mid_price'] / dte if dte > 0 else 0
            
            # Calculate annualized yield
            if is_put:
                annualized_yield = (opt['mid_price'] / strike) * (365 / dte) * 100
                roc = (opt['mid_price'] / strike) * 100  # ROC for CSPs
                monthly_roc = roc * (30 / dte)  # Monthly ROC
                break_even = strike - opt['mid_price']
            else:
                annualized_yield = (opt['mid_price'] / current_price) * (365 / dte) * 100
                roc = (opt['mid_price'] / current_price) * 100  # ROC for covered calls
                monthly_roc = roc * (30 / dte)  # Monthly ROC
                break_even = strike + opt['mid_price']
            
            # Skip if yield is too low
            if annualized_yield < MIN_ANNUALIZED_YIELD:
                continue
                
            # Skip if monthly ROC is too low
            if monthly_roc < MIN_ROC:
                continue
            
            # Calculate probability ITM (using delta as proxy)
            probability_itm = delta * 100  # Convert to percentage
            
            # Skip if probability ITM is too low
            if probability_itm < MIN_PROBABILITY_ITM:
                continue
            
            # Calculate risk/reward ratio
            if is_put:
                max_risk = strike - opt['mid_price']
                max_reward = opt['mid_price']
            else:
                max_risk = float('inf')  # Unlimited risk for naked calls
                max_reward = opt['mid_price']
            
            risk_reward_ratio = (max_reward / max_risk) if max_risk > 0 else float('inf')
            
            # Add calculated metrics to option dict
            opt.update({
                'annualized_yield': annualized_yield,
                'return_on_capital': roc,
                'monthly_roc': monthly_roc,
                'annualized_roc': monthly_roc * 12,  # Annualized ROC
                'premium_per_day': premium_per_day,
                'break_even': break_even,
                'probability_itm': probability_itm,
                'risk_reward_ratio': risk_reward_ratio,
                'spread_pct': spread_pct,
                'days_to_expiration': dte,
                'strike_pct_otm': -strike_pct if is_put else strike_pct,
                'type': 'Put' if is_put else 'Call'
            })
            
            filtered.append(opt)
            
        except Exception as e:
            print(f"⚠️ Error processing option: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Sort by the selected ranking metric
    if filtered:
        print(f"✅ Found {len(filtered)} viable {option_type} trades")
        
        # Define ranking metrics (higher is better)
        rank_metrics = {
            'annualized_yield': lambda x: x.get('annualized_yield', 0),
            'annualized_roc': lambda x: x.get('annualized_roc', 0),
            'premium_per_day': lambda x: x.get('premium_per_day', 0),
            'risk_reward': lambda x: x.get('risk_reward_ratio', 0),
            'probability_itm': lambda x: x.get('probability_itm', 0)
        }
        
        # Sort by the selected metric (descending)
        if TRADE_RANK_METRIC in rank_metrics:
            filtered.sort(key=rank_metrics[TRADE_RANK_METRIC], reverse=True)
        else:
            # Default sort by annualized ROC
            filtered.sort(key=rank_metrics['annualized_roc'], reverse=True)
        
        # Limit to top N trades
        filtered = filtered[:MAX_TRADES_PER_TYPE]
    else:
        print(f"⚠️ No {option_type} options passed all filters")
    
    return filtered

def generate_trade_idea_sheet(puts: List[Dict], calls: List[Dict], output_dir: str = 'output', simulate_forward: bool = True) -> str:
    """
    Generate a markdown report with the best trading opportunities.
    
    Args:
        puts: List of filtered put options
        calls: List of filtered call options
        output_dir: Directory to save the report
        simulate_forward: Whether to simulate forward or backtest
        
    Returns:
        Path to the generated report
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(output_dir, f'trade_ideas_{timestamp}.md')
    
    # Prepare markdown content
    md_content = [
        "# 📊 Daily Options Trade Ideas",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## 📈 Market Overview",
        "*Market data as of latest close*\n"
    ]
    
    # Get current prices for all tickers
    underlying_prices = {}
    for option in puts + calls:
        ticker = option.get('ticker')
        price = option.get('underlying_price')
        if ticker and price:
            underlying_prices[ticker] = price
    
    # Simulate top trades
    top_puts = puts[:5]  # Top 5 puts for simulation
    top_calls = calls[:5]  # Top 5 calls for simulation
    
    # Add simulation data to top trades
    simulated_puts = simulate_recommended_trades(top_puts, underlying_prices, simulate_forward)
    simulated_calls = simulate_recommended_trades(top_calls, underlying_prices, simulate_forward)
    
    # Update the original lists with simulation results
    for i, put in enumerate(simulated_puts):
        if i < len(puts):
            puts[i].update(put)
    
    for i, call in enumerate(simulated_calls):
        if i < len(calls):
            calls[i].update(call)
    
    # Add best puts section
    md_content.extend([
        "\n## 💰 Best Cash-Secured Puts",
        "| Ticker | Price | Strike | Premium | Yield | Annualized | DTE | Prob ITM | Sim. Profit % | Sim. Max DD % |",
        "|--------|-------|--------|---------|-------|------------|-----|----------|---------------|---------------|"
    ])
    
    for put in puts[:10]:  # Top 10 puts
        sim = put.get('simulation', {})
        md_content.append(
            f"| {put.get('ticker', 'N/A')} | "
            f"${put.get('underlying_price', 0):.2f} | "
            f"${put.get('strike_price', 0):.2f} | "
            f"${put.get('mid_price', 0):.2f} | "
            f"{put.get('premium_yield', 0):.1f}% | "
            f"{put.get('annualized_yield', 0):.1f}% | "
            f"{put.get('days_to_expiration', 0)} | "
            f"{put.get('probability_itm', 0):.1f}% | "
            f"{sim.get('realized_yield', 'N/A'):.1f}% | "
            f"{abs(sim.get('max_drawdown', 0)):.1f}% |"
        )
    
    # Add best calls section
    md_content.extend([
        "\n## 📈 Best Covered Calls",
        "| Ticker | Price | Strike | Premium | Yield | Annualized | DTE | Prob ITM | Sim. Profit % | Sim. Max DD % |",
        "|--------|-------|--------|---------|-------|------------|-----|----------|---------------|---------------|"
    ])
    
    for call in calls[:10]:  # Top 10 calls
        sim = call.get('simulation', {})
        md_content.append(
            f"| {call.get('ticker', 'N/A')} | "
            f"${call.get('underlying_price', 0):.2f} | "
            f"${call.get('strike_price', 0):.2f} | "
            f"${call.get('mid_price', 0):.2f} | "
            f"{call.get('premium_yield', 0):.1f}% | "
            f"{call.get('annualized_yield', 0):.1f}% | "
            f"{call.get('days_to_expiration', 0)} | "
            f"{call.get('probability_itm', 0):.1f}% | "
            f"{sim.get('realized_yield', 'N/A'):.1f}% | "
            f"{abs(sim.get('max_drawdown', 0)):.1f}% |"
        )
    
    # Add trade recommendations with simulation results
    md_content.extend([
        "\n## 🎯 Top Trade Recommendations with Simulation"
    ])
    
    # Best Put recommendation with simulation
    if puts and 'simulation' in puts[0]:
        put = puts[0]
        sim = put['simulation']
        md_content.extend([
            "### 1. Best Overall Put",
            f"- **{put['ticker']}** ${put['strike_price']:.2f} Put @ ${put['mid_price']:.2f}",
            f"- **Entry Price:** ${put.get('underlying_price', 0):.2f}",
            f"- **Expiration:** {put.get('expiration', 'N/A')} (in {put.get('days_to_expiration', 0)} days)",
            f"- **Premium Yield:** {put.get('premium_yield', 0):.1f}% ({put.get('annualized_yield', 0):.1f}% annualized)",
            f"- **Simulated Profit:** {sim.get('realized_yield', 'N/A'):.1f}% (Max DD: {abs(sim.get('max_drawdown', 0)):.1f}%)",
            f"- **Prob. Profit:** {sim.get('probability_of_profit', 'N/A')}% | **Breakeven:** ${sim.get('breakeven', 'N/A'):.2f}",
            f"- **Simulated Exit:** ${sim.get('exit_price', 'N/A'):.2f} after {sim.get('held_days', 'N/A')} days"
        ])
    
    # Best Call recommendation with simulation
    if calls and 'simulation' in calls[0]:
        call = calls[0]
        sim = call['simulation']
        md_content.extend([
            "\n### 2. Best Overall Call",
            f"- **{call['ticker']}** ${call['strike_price']:.2f} Call @ ${call['mid_price']:.2f}",
            f"- **Entry Price:** ${call.get('underlying_price', 0):.2f}",
            f"- **Expiration:** {call.get('expiration', 'N/A')} (in {call.get('days_to_expiration', 0)} days)",
            f"- **Premium Yield:** {call.get('premium_yield', 0):.1f}% ({call.get('annualized_yield', 0):.1f}% annualized)",
            f"- **Simulated Profit:** {sim.get('realized_yield', 'N/A'):.1f}% (Max DD: {abs(sim.get('max_drawdown', 0)):.1f}%)",
            f"- **Prob. Profit:** {sim.get('probability_of_profit', 'N/A')}% | **Breakeven:** ${sim.get('breakeven', 'N/A'):.2f}",
            f"- **Simulated Exit:** ${sim.get('exit_price', 'N/A'):.2f} after {sim.get('held_days', 'N/A')} days"
        ])
    
    # Add notes and disclaimers
    md_content.extend([
        "\n## 📝 Notes & Disclaimers",
        "- **All metrics** are calculated based on mid-price between bid and ask.",
        "- **Prob ITM** is estimated using delta as a proxy.",
        "- **Simulation results** are based on historical data and mathematical models, not guarantees of future performance.",
        "- **Max Drawdown (DD)** shows the maximum observed decline from peak value during the simulation period.",
        "- **Always** consider your risk tolerance and do your own research before trading.",
        "- **Past performance** is not indicative of future results.",
        f"- **Simulation mode:** {'Forward' if simulate_forward else 'Backtest'} simulation"
    ])
    
    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(line for line in md_content if line is not None))
    
    return filename

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

def save_to_markdown(ticker: str, price: float, puts: List[Dict] = None, calls: List[Dict] = None, filename: str = None) -> str:
    """
    Save options analysis to a markdown file with enhanced metrics.
    
    Args:
        ticker: Stock ticker symbol
        price: Current stock price
        puts: List of put option dictionaries
        calls: List of call option dictionaries
        filename: Output filename (default: 'output/{ticker}_analysis_YYYYMMDD_HHMMSS.md')
        
    Returns:
        Path to the saved file
    """
    # Handle default arguments
    if puts is None:
        puts = []
    if calls is None:
        calls = []
        
    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)
    
    # Generate filename if not provided
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'output/{ticker}_analysis_{timestamp}.md'
    
    # Prepare markdown content
    md_content = [
        f"# 📊 Options Analysis: {ticker}",
        f"**Current Price:** ${price:.2f}  ",
        f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    ]
    
    # Add puts section if available
    if puts:
        md_content.extend([
            "## 💰 Put Options",
            "| Strike | Premium | Δ | Yield | Annualized | ROC | DTE | Prob ITM | R/R | OI | Volume |",
            "|--------|---------|--|-------|------------|-----|-----|----------|-----|----|--------|"
        ])
        
        # Sort puts by annualized yield and take top 20
        for put in sorted(puts, key=lambda x: x.get('annualized_yield', 0), reverse=True)[:20]:
            md_content.append(
                f"| ${put.get('strike_price', 0):.2f} | "
                f"${put.get('mid_price', 0):.2f} | "
                f"{put.get('delta', 0):.2f} | "
                f"{put.get('premium_yield', 0):.1f}% | "
                f"{put.get('annualized_yield', 0):.1f}% | "
                f"{put.get('monthly_roc', 0):.1f}% | "
                f"{put.get('days_to_expiration', 0)} | "
                f"{put.get('probability_itm', 0):.1f}% | "
                f"1:{put.get('risk_reward_ratio', 0):.1f} | "
                f"{put.get('open_interest', 0):,} | "
                f"{put.get('volume', 0):,} |"
            )
    else:
        md_content.append("\nNo qualifying put options found.\n")
    
    # Add calls section if available
    if calls:
        md_content.extend([
            "\n## 📈 Call Options",
            "| Strike | Premium | Δ | Yield | Annualized | ROC | DTE | Prob ITM | R/R | OI | Volume |",
            "|--------|---------|--|-------|------------|-----|-----|----------|-----|----|--------|"
        ])
        
        # Sort calls by annualized yield and take top 20
        for call in sorted(calls, key=lambda x: x.get('annualized_yield', 0), reverse=True)[:20]:
            md_content.append(
                f"| ${call.get('strike_price', 0):.2f} | "
                f"${call.get('mid_price', 0):.2f} | "
                f"{call.get('delta', 0):.2f} | "
                f"{call.get('premium_yield', 0):.1f}% | "
                f"{call.get('annualized_yield', 0):.1f}% | "
                f"{call.get('monthly_roc', 0):.1f}% | "
                f"{call.get('days_to_expiration', 0)} | "
                f"{call.get('probability_itm', 0):.1f}% | "
                f"1:{call.get('risk_reward_ratio', 0):.1f} | "
                f"{call.get('open_interest', 0):,} | "
                f"{call.get('volume', 0):,} |"
            )
    else:
        md_content.append("\nNo qualifying call options found.\n")
    
    # Add footer with timestamp
    md_content.append(f"\n*Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}*")
    
    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_content))
    
    return filename

def print_header():
    """Print analysis header with market status"""
    print("\n" + "="*80)
    print(f"📊 OPTIONS SCREENER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*80)
    
    market_status = get_market_status()
    status_msg = f"✅ Market is currently {'open' if market_status == 'open' else 'closed'}" if market_status else "❓ Market status unknown"
    
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
    """
    Main function to run the options analysis.
    
    This function:
    1. Sets up the output directory and initializes tracking variables
    2. Processes each ticker in TICKERS list
    3. Fetches and analyzes options data for each ticker
    4. Generates and saves markdown reports
    5. Handles errors and provides summary statistics
    """
    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)
    
    # Get current timestamp for the output file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'output/options_analysis_{timestamp}.md'
    
    # Initialize stats
    stats = {
        'tickers_processed': 0,
        'tickers_with_puts': 0,
        'tickers_with_calls': 0,
        'tickers_with_errors': 0,
        'total_puts_found': 0,
        'total_calls_found': 0,
        'start_time': datetime.now(),
        'errors': []
    }
    
    all_puts = []
    all_calls = []
    
    # Print header and get initial markdown content
    md_content = print_header()
    
    print("="*80)
    print(f"🚀 Starting options analysis for {len(TICKERS)} tickers")
    print(f"⏰ {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Add ticker list to markdown
    md_content.extend([
        "## 📋 Tickers Analyzed",
        "",
        "| Ticker | Status | Puts Found | Calls Found | Error |",
        "|--------|--------|------------|-------------|-------|"
    ])
    
    # Process each ticker
    for ticker in TICKERS:
        ticker_start = datetime.now()
        stats['tickers_processed'] += 1
        ticker_status = ""
        ticker_error = ""
        puts_found = 0
        calls_found = 0
        price = None
        options_chain = None
        
        try:
            print(f"\n{'='*80}\n📊 [{stats['tickers_processed']}/{len(TICKERS)}] Analyzing {ticker}")
            print("-"*80)
            
            # Get stock price
            print(f"🔍 Fetching current price for {ticker}...")
            price = get_stock_price(ticker)
            if not price or price <= 0:
                raise ValueError(f"Invalid price ${price:.2f} for {ticker}")
            
            print(f"✅ Current price: ${price:.2f}")
            
            # Get options chain with progress indication
            print(f"🔍 Fetching options chain for {ticker}...")
            # First get puts
            puts_chain = get_options_chain(ticker, 'put', price)
            # Then get calls
            calls_chain = get_options_chain(ticker, 'call', price)
            
            # Combine the results
            options_chain = {'results': []}
            if puts_chain and 'results' in puts_chain:
                options_chain['results'].extend(puts_chain['results'])
            if calls_chain and 'results' in calls_chain:
                options_chain['results'].extend(calls_chain['results'])
                
            if not options_chain['results']:
                raise ValueError("No valid options found for either puts or calls")
                
            print(f"✅ Found {len(options_chain.get('results', []))} options contracts")
            
            # Process puts and calls
            print(f"📊 Processing options data for {ticker}...")
            
            try:
                # Process and filter options
                puts, calls = process_options_chain(options_chain, price)
                
                # Update stats and collections
                if puts:
                    all_puts.extend(puts)
                    puts_found = len(puts)
                    stats['tickers_with_puts'] += 1
                    stats['total_puts_found'] += puts_found
                    print(f"✅ Found {puts_found} qualifying put options")
                    
                if calls:
                    all_calls.extend(calls)
                    calls_found = len(calls)
                    stats['tickers_with_calls'] += 1
                    stats['total_calls_found'] += calls_found
                    print(f"✅ Found {calls_found} qualifying call options")
                
                if not puts and not calls:
                    ticker_status = "⚠️ No qualifying options"
                    print(ticker_status)
                else:
                    ticker_status = "✅ Success"
                
                # Add ticker results to markdown
                md_content.append(f"| {ticker} | {ticker_status} | {puts_found} | {calls_found} | {ticker_error[:50] + '...' if ticker_error else ''} |")
                
                # Add PUT results
                if puts:
                    md_content.extend([
                        f"\n### 📉 PUT Options",
                        "| Strike | Premium | Δ | Yield | Annualized | ROC | DTE | Prob ITM | R/R | OI | Volume |",
                        "|--------|---------|--|-------|------------|-----|-----|----------|-----|----|--------|"
                    ])
                    for put in sorted(puts, key=lambda x: x.get('strike_price', 0)):
                        md_content.append(
                            f"| ${put.get('strike_price', 0):.2f} | "
                            f"${put.get('mid_price', 0):.2f} | "
                            f"{put.get('delta', 0):.2f} | "
                            f"{put.get('premium_yield', 0):.1f}% | "
                            f"{put.get('annualized_yield', 0):.1f}% | "
                            f"{put.get('monthly_roc', 0):.1f}% | "
                            f"{put.get('days_to_expiration', 0)} | "
                            f"{put.get('probability_itm', 0):.1f}% | "
                            f"1:{put.get('risk_reward_ratio', 0):.1f} | "
                            f"{put.get('open_interest', 0):,} | "
                            f"{put.get('volume', 0):,} |"
                        )
                
                # Add CALL results
                if calls:
                    md_content.extend([
                        f"\n### 📈 CALL Options",
                        "| Strike | Premium | Δ | Yield | Annualized | ROC | DTE | Prob ITM | R/R | OI | Volume |",
                        "|--------|---------|--|-------|------------|-----|-----|----------|-----|----|--------|"
                    ])
                    for call in sorted(calls, key=lambda x: x.get('strike_price', 0)):
                        md_content.append(
                            f"| ${call.get('strike_price', 0):.2f} | "
                            f"${call.get('mid_price', 0):.2f} | "
                            f"{call.get('delta', 0):.2f} | "
                            f"{call.get('premium_yield', 0):.1f}% | "
                            f"{call.get('annualized_yield', 0):.1f}% | "
                            f"{call.get('monthly_roc', 0):.1f}% | "
                            f"{call.get('days_to_expiration', 0)} | "
                            f"{call.get('probability_itm', 0):.1f}% | "
                            f"1:{call.get('risk_reward_ratio', 0):.1f} | "
                            f"{call.get('open_interest', 0):,} | "
                            f"{call.get('volume', 0):,} |"
                        )
                
                # Add separator between tickers
                md_content.append("\n---\n")
                
            except Exception as e:
                error_msg = f"❌ Error processing {ticker}: {str(e)}"
                print(error_msg)
                stats['errors'].append(error_msg)
                md_content.append(f"| {ticker} | ❌ Error | 0 | 0 | {str(e)[:50]}... |")
                stats['tickers_with_errors'] += 1
                continue
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            error_msg = f"❌ Error fetching data for {ticker}: {str(e)}"
            print(error_msg)
            stats['errors'].append(error_msg)
            md_content.append(f"| {ticker} | ❌ Error | 0 | 0 | {str(e)[:50]}... |")
            stats['tickers_with_errors'] += 1
            continue
    
    # After processing all tickers, add summary section
    md_content.extend([
        "\n## 📊 Analysis Summary",
        f"- **Total tickers processed:** {stats['tickers_processed']}",
        f"- **Tickers with qualifying puts:** {stats['tickers_with_puts']}",
        f"- **Tickers with qualifying calls:** {stats['tickers_with_calls']}",
        f"- **Total puts found:** {stats['total_puts_found']}",
        f"- **Total calls found:** {stats['total_calls_found']}",
        f"- **Tickers with errors:** {stats['tickers_with_errors']}",
        f"- **Total runtime:** {datetime.now() - stats['start_time']}",
        "",
        "## 🔍 Top Trades by Annualized Yield"
    ])
    
    # Add top puts
    if all_puts:
        md_content.extend([
            "\n### 🏆 Top 5 Cash-Secured Puts",
            "| Ticker | Strike | Premium | Δ | Yield | Annualized | ROC | DTE | Prob ITM | R/R |",
            "|--------|--------|---------|--|-------|------------|-----|-----|----------|-----|"
        ])
        for put in sorted(all_puts, key=lambda x: x.get('annualized_yield', 0), reverse=True)[:5]:
            md_content.append(
                f"| {put.get('ticker', 'N/A')} | "
                f"${put.get('strike_price', 0):.2f} | "
                f"${put.get('mid_price', 0):.2f} | "
                f"{put.get('delta', 0):.2f} | "
                f"{put.get('premium_yield', 0):.1f}% | "
                f"{put.get('annualized_yield', 0):.1f}% | "
                f"{put.get('monthly_roc', 0):.1f}% | "
                f"{put.get('days_to_expiration', 0)} | "
                f"{put.get('probability_itm', 0):.1f}% | "
                f"1:{put.get('risk_reward_ratio', 0):.1f} |"
            )
    
    # Add top calls
    if all_calls:
        md_content.extend([
            "\n### 🏆 Top 5 Covered Calls",
            "| Ticker | Strike | Premium | Δ | Yield | Annualized | ROC | DTE | Prob ITM | R/R |",
            "|--------|--------|---------|--|-------|------------|-----|-----|----------|-----|"
        ])
        for call in sorted(all_calls, key=lambda x: x.get('annualized_yield', 0), reverse=True)[:5]:
            md_content.append(
                f"| {call.get('ticker', 'N/A')} | "
                f"${call.get('strike_price', 0):.2f} | "
                f"${call.get('mid_price', 0):.2f} | "
                f"{call.get('delta', 0):.2f} | "
                f"{call.get('premium_yield', 0):.1f}% | "
                f"{call.get('annualized_yield', 0):.1f}% | "
                f"{call.get('monthly_roc', 0):.1f}% | "
                f"{call.get('days_to_expiration', 0)} | "
                f"{call.get('probability_itm', 0):.1f}% | "
                f"1:{call.get('risk_reward_ratio', 0):.1f} |"
            )
    
    # Add errors if any
    if stats['errors']:
        md_content.extend([
            "\n## ❌ Errors Encountered",
            "The following errors were encountered during processing:"
        ])
        for error in stats['errors']:
            md_content.append(f"- {error}")
    
    # Add footer
    md_content.extend([
        "",
        "---",
        f"Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S %Z')}",
        ""
    ])
    
    # Save to file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_content))
        print(f"\n✅ Analysis complete! Results saved to {output_file}")
        
        # Generate trade idea sheet
        trade_idea_file = generate_trade_idea_sheet(all_puts, all_calls)
        if trade_idea_file:
            print(f"📋 Trade idea sheet saved to {trade_idea_file}")
            
    except Exception as e:
        print(f"❌ Error saving results: {str(e)}")
    
    # Add final summary statistics
    stats['end_time'] = datetime.now()
    stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds() / 60
    
    md_content.extend([
        "\n## 📊 Final Summary",
        f"- **Tickers Processed:** {stats['tickers_processed']}",
        f"- **Tickers with Valid Puts:** {stats['tickers_with_puts']}",
        f"- **Tickers with Valid Calls:** {stats['tickers_with_calls']}",
        f"- **Total Puts Found:** {stats['total_puts_found']}",
        f"- **Total Calls Found:** {stats['total_calls_found']}",
        f"- **Tickers with Errors:** {stats['tickers_with_errors']}",
        f"- **Total Runtime:** {stats['duration']:.1f} minutes",
        ""
    ])
    
    # Add any errors encountered
    if stats['errors']:
        md_content.extend([
            "## ❌ Errors Encountered",
            "The following errors were encountered during processing:"
        ])
        for error in stats['errors']:
            md_content.append(f"- {error}")
    
    # Add footer
    md_content.extend([
        "",
        "---",
        f"Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S %Z')}",
        ""
    ])
    
    # Save the final markdown file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_content))
        print(f"\n✅ Final analysis saved to {output_file}")
    except Exception as e:
        print(f"❌ Error saving final results: {str(e)}")
    
    # Generate trade idea sheet if we have valid options
    if all_puts or all_calls:
        trade_sheet_path = generate_trade_idea_sheet(all_puts, all_calls)
        if trade_sheet_path:
            print(f"📊 Trade idea sheet generated: {os.path.abspath(trade_sheet_path)}")
    
    print(f"\n{'='*80}\n✅ Analysis complete!")
    print(f"📄 Report saved to: {os.path.abspath(output_file)}")
    if 'trade_sheet_path' in locals() and trade_sheet_path:
        print(f"📊 Trade ideas saved to: {os.path.abspath(trade_sheet_path)}")
    print("="*80)
    
    return output_file

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrupted by user")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
