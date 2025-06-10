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

# Default filter parameters - can be overridden by command line
DEFAULT_MIN_PREMIUM = 0.50  # Minimum premium to consider
DEFAULT_MIN_ANNUALIZED_YIELD = 20.0  # Minimum annualized yield percentage
DEFAULT_MIN_ROC = 1.0  # Minimum return on capital (monthly)
DEFAULT_MIN_PROBABILITY_ITM = 30.0  # Minimum probability ITM percentage
DEFAULT_MIN_DELTA = 0.15  # Minimum delta for puts (absolute value)
DEFAULT_MAX_DELTA = 0.45  # Maximum delta for puts (absolute value)
DEFAULT_MIN_OPEN_INTEREST = 100  # Minimum open interest

# Global variables that can be modified at runtime
TARGET_EXPIRATION = None  # Will be set dynamically
MIN_PREMIUM = DEFAULT_MIN_PREMIUM
MIN_ANNUALIZED_YIELD = DEFAULT_MIN_ANNUALIZED_YIELD
MIN_ROC = DEFAULT_MIN_ROC
MIN_PROBABILITY_ITM = DEFAULT_MIN_PROBABILITY_ITM
MIN_DELTA = DEFAULT_MIN_DELTA
MAX_DELTA = DEFAULT_MAX_DELTA
MIN_OPEN_INTEREST = DEFAULT_MIN_OPEN_INTEREST

# Options filtering parameters
MIN_STRIKE_PCT = 0.90  # 10% below current price for puts
MAX_STRIKE_PCT = 1.10  # 10% above current price for calls
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
        dict: Dictionary containing options data or empty dict on failure
    """
    if not ticker or not option_type or not current_price or current_price <= 0:
        print(f"❌ Invalid input parameters for get_options_chain: ticker={ticker}, "
              f"option_type={option_type}, price={current_price}")
        return {'results': []}
        
    option_type = option_type.lower()
    if option_type not in ['put', 'call']:
        print(f"❌ Invalid option_type: {option_type}. Must be 'put' or 'call'")
        return {'results': []}
    if not API_KEY or API_KEY == 'YOUR_API_KEY_HERE':
        print("⚠️  Please set your Polygon.io API key in the environment variable POLYGON_API_KEY")
        return []
    
    print(f"\n{'='*60}")
    print(f"FETCHING {option_type.upper()} OPTIONS FOR {ticker.upper()}")
    print(f"Current Price: ${current_price:.2f}")
    
    # Calculate strike price range based on configured percentages
    if option_type == 'put':
        min_strike = current_price * MIN_STRIKE_PCT
        max_strike = current_price  # Up to current price for puts
    else:  # call
        min_strike = current_price  # From current price for calls
        max_strike = current_price * MAX_STRIKE_PCT
    
    print(f"Fetching {option_type} options with strikes ${min_strike:.2f} to ${max_strike:.2f}...")
    
    # Prepare request parameters
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        'underlying_ticker': ticker,
        'contract_type': option_type,
        'expiration_date': TARGET_EXPIRATION,
        'limit': 1000,  # Increased limit to get more strikes
        'as_of': 'trades',  # Get most recent trade data
        'sort': 'strike_price',
        'order': 'asc',
        'apiKey': API_KEY  # Ensure API key is included
    }
    
    # Add a user agent to help with rate limiting
    headers = {
        'User-Agent': 'BenOptionsScanner/1.0',
        'Authorization': f'Bearer {API_KEY}'
    }
    
    # Add retry logic with exponential backoff and jitter
    for attempt in range(max_retries):
        try:
            # Add jitter to avoid thundering herd problem
            delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
            if attempt > 0:
                print(f"⏳ Retry attempt {attempt}/{max_retries-1} in {delay:.1f} seconds...")
                time.sleep(delay)
                
            print(f"🔍 Request #{attempt+1} for {ticker} {option_type.upper()} options:")
            print(f"   URL: {url}")
            print(f"   Params: {params}")
            
            # Add timeout and better error handling
            response = requests.get(
                url, 
                params=params, 
                headers=headers, 
                timeout=15  # Increased timeout
            )
            
            print(f"✅ Response received in {response.elapsed.total_seconds():.2f}s (Status: {response.status_code})")
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', min(delay * 2, 60)))  # Cap at 60s
                print(f"⚠️  Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue
                
            # Handle other HTTP errors
            response.raise_for_status()
            
            # Parse response
            try:
                data = response.json()
            except ValueError as e:
                print(f"❌ Failed to parse JSON response: {e}")
                if attempt < max_retries - 1:
                    continue
                return {'results': []}
            
            # Process the options chain
            if 'results' not in data or not data['results']:
                print(f"ℹ️  No {option_type} options found for {ticker}")
                return {'results': []}
                
            # Filter options by strike price range and add additional metrics
            filtered_options = []
            valid_options = 0
            
            for option in data['results']:
                try:
                    strike_price = float(option.get('strike_price', 0))
                    if strike_price <= 0:
                        continue
                        
                    # Calculate moneyness
                    if option_type == 'put':
                        moneyness = (strike_price / current_price) - 1  # Negative for ITM, positive for OTM
                        is_itm = strike_price > current_price
                    else:  # call
                        moneyness = (strike_price / current_price) - 1  # Negative for OTM, positive for ITM
                        is_itm = strike_price < current_price
                    
                    # Filter by strike price range
                    if min_strike <= strike_price <= max_strike:
                        # Add additional metrics
                        option['ticker'] = ticker
                        option['option_type'] = option_type
                        option['current_price'] = current_price
                        option['moneyness'] = moneyness
                        option['is_itm'] = is_itm
                        
                        # Calculate days to expiration
                        if 'expiration_date' in option:
                            try:
                                exp_date = datetime.strptime(option['expiration_date'], '%Y-%m-%d')
                                dte = (exp_date - datetime.now()).days
                                option['days_to_expiration'] = max(1, dte)  # Ensure at least 1 day
                            except (ValueError, TypeError):
                                option['days_to_expiration'] = 30  # Default if parsing fails
                        else:
                            option['days_to_expiration'] = 30  # Default if not provided
                        
                        # Add Greeks if available
                        if 'greeks' in option and isinstance(option['greeks'], dict):
                            option.update(option['greeks'])
                        
                        filtered_options.append(option)
                        valid_options += 1
                        
                except (KeyError, ValueError, TypeError) as e:
                    print(f"⚠️  Error processing option: {e}")
                    continue
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
        print("❌ No options provided for summarization")
        return []
    
    option_type = 'PUT' if is_put else 'CALL'
    print(f"\n{'='*60}")
    print(f"📊 SUMMARIZING {option_type} OPTIONS (Current Price: ${current_price:.2f})")
    print(f"Processing {len(options)} options...")
    print("-"*60)
    
    processed_options = []
    skipped_count = 0
    
    # Track reasons for skipping options
    skip_reasons = {
        'no_pricing': 0,
        'expired': 0,
        'invalid_strike': 0,
        'invalid_expiration': 0,
        'missing_data': 0,
        'other': 0
    }
    
    for i, contract in enumerate(options):
        try:
            # Skip if no pricing data
            if not contract.get('last_quote'):
                skip_reasons['no_pricing'] += 1
                skipped_count += 1
                continue
            
            # Get strike price and expiration
            strike = contract.get('strike_price')
            expiration = contract.get('expiration_date')
            
            # Validate strike price
            if not strike or strike <= 0:
                skip_reasons['invalid_strike'] += 1
                skipped_count += 1
                continue
            
            # Calculate days to expiration
            dte = 0
            if expiration:
                try:
                    expiration_date = datetime.strptime(expiration, '%Y-%m-%d').date()
                    dte = (expiration_date - date.today()).days
                    if dte <= 0:  # Skip expired options
                        skip_reasons['expired'] += 1
                        skipped_count += 1
                        continue
                except (ValueError, TypeError) as e:
                    skip_reasons['invalid_expiration'] += 1
                    skipped_count += 1
                    continue
            else:
                skip_reasons['missing_data'] += 1
                skipped_count += 1
                continue
            
            # Get bid/ask/last prices with fallbacks
            last_quote = contract.get('last_quote', {}) or {}
            bid = float(last_quote.get('bid', 0) or 0)
            ask = float(last_quote.get('ask', 0) or 0)
            last = float(last_quote.get('last', 0) or 0)
            
            # Skip if no valid pricing data
            if bid <= 0 and ask <= 0 and last <= 0:
                skip_reasons['no_pricing'] += 1
                skipped_count += 1
                continue
            
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
    
    # Print summary of processed options
    print("\n" + "="*60)
    print(f"✅ PROCESSED {len(processed_options)} {option_type} OPTIONS")
    print(f"❌ SKIPPED {skipped_count} options:")
    
    # Only show skip reasons that have a count > 0
    for reason, count in skip_reasons.items():
        if count > 0:
            reason_display = reason.replace('_', ' ').title()
            print(f"  - {reason_display}: {count}")
    
    # Print top 3 strikes that made it through
    if processed_options:
        print("\n🔝 TOP 3 OPPORTUNITIES BY PREMIUM YIELD:")
        sorted_options = sorted(processed_options, key=lambda x: x.get('annualized_yield', 0), reverse=True)[:3]
        for i, opt in enumerate(sorted_options, 1):
            print(f"  {i}. ${opt['strike_price']} {option_type} | "
                  f"${opt.get('mid_price', 0):.2f} | "
                  f"Δ {abs(opt.get('delta', 0)):.2f} | "
                  f"{opt.get('annualized_yield', 0):.1f}% yield | "
                  f"{opt.get('days_to_expiration', 0)} DTE")
    
    print("="*60 + "\n")
    
    if not processed_options:
        print("No valid options found after processing")
    
    # Filter and sort the options
    return filter_and_sort_options(processed_options, current_price, is_put)

def filter_and_sort_options(options: List[Dict], current_price: float, is_put: bool = True, 
                          risk_tolerance: str = 'medium') -> List[Dict]:
    """
    Filter and sort options based on advanced criteria and rank them for potential trades.
    
    Args:
        options: List of option dictionaries with pricing and greeks
        current_price: Current price of the underlying asset
        is_put: Whether these are put options (True) or call options (False)
        risk_tolerance: Risk tolerance level ('low', 'medium', 'high')
        
    Returns:
        List of filtered and ranked option dictionaries with additional metrics
    """
    if not options:
        print("No options provided for filtering.")
        return []
    
    # Set risk-based parameters
    risk_params = {
        'low': {
            'pop_min': 0.75,
            'delta_min': 0.30 if is_put else 0.15,
            'delta_max': 0.70 if is_put else 0.50,
            'min_premium_mod': 1.5,  # Higher premium for lower risk
            'spread_max': 0.15,  # Tighter spreads
            'tag': '💰 Income'
        },
        'medium': {
            'pop_min': 0.50,
            'delta_min': 0.15 if is_put else 0.05,
            'delta_max': 0.85 if is_put else 0.70,
            'min_premium_mod': 1.0,
            'spread_max': 0.30,
            'tag': '📈 Directional'
        },
        'high': {
            'pop_min': 0.30,
            'delta_min': 0.05 if is_put else 0.01,
            'delta_max': 0.95 if is_put else 0.90,
            'min_premium_mod': 0.5,  # Accept lower premiums
            'spread_max': 0.50,  # Wider spreads allowed
            'tag': '🎯 Speculative'
        }
    }
    
    # Get parameters based on risk tolerance
    params = risk_params.get(risk_tolerance.lower(), risk_params['medium'])
    
    # Apply risk-based adjustments
    min_delta = max(MIN_DELTA, params['delta_min'])
    max_delta = min(MAX_DELTA, params['delta_max'])
    min_premium = MIN_PREMIUM * params['min_premium_mod']
    min_open_interest = max(MIN_OPEN_INTEREST, 50)  # Higher OI for lower risk
    
    option_type = 'Put' if is_put else 'Call'
    
    print(f"\n🔍 Filtering {option_type} options (Risk: {risk_tolerance.upper()} - {params['tag']}):")
    print(f"  - Delta range: {min_delta:.2f}-{max_delta:.2f}")
    print(f"  - Min premium: ${min_premium:.2f}")
    print(f"  - Min open interest: {min_open_interest}")
    print(f"  - Min probability ITM: {params['pop_min']*100:.0f}%")
    print(f"  - Max bid-ask spread: {params['spread_max']*100:.0f}%")
    print(f"  - Strike range: {MIN_STRIKE_PCT*100:.1f}% to {MAX_STRIKE_PCT*100:.1f}% of current price")
    
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
            
            # Skip if strike is outside our defined percentage range
            strike_pct = strike / current_price
            if is_put and (strike_pct < MIN_STRIKE_PCT or strike_pct > 1.0):
                continue
            elif not is_put and (strike_pct > MAX_STRIKE_PCT or strike_pct < 1.0):
                continue
            
            # Skip if open interest is too low
            if opt['open_interest'] < min_open_interest:
                continue
                
            # Skip if premium is too low
            if opt.get('mid_price', 0) < min_premium:
                continue
            
            # Calculate bid-ask spread as % of mid price
            spread = opt['ask'] - opt['bid']
            mid_price = opt.get('mid_price', (opt['bid'] + opt['ask']) / 2) if opt['bid'] and opt['ask'] else opt.get('last_trade_price', 0)
            spread_pct = (spread / mid_price * 100) if mid_price > 0 else 100
            
            # Debug log for each option that passes all filters
            print(f"  ✓ {option_type.upper()} {strike} | Δ {delta:.2f} | ${mid_price:.2f} | OI: {opt['open_interest']} | Vol: {opt['volume']}")
            print(f"     Bid/Ask: ${opt.get('bid', 0):.2f}/${opt.get('ask', 0):.2f} | Spread: {spread_pct:.1f}% | DTE: {opt.get('days_to_expiration', 'N/A')}")
            
            # Skip if spread is too wide
            if spread_pct > MAX_BID_ASK_SPREAD_PCT:
                continue
            
            # Calculate days to expiration
            dte = max(1, opt.get('days_to_expiration', 30))
            
            # Calculate probability ITM (using delta's absolute value as proxy)
            probability_itm = abs(delta)
            
            # Skip if probability ITM is below threshold for risk tolerance
            if probability_itm < params['pop_min']:
                print(f"  ✗ ${strike} | Probability ITM {probability_itm*100:.1f}% < {params['pop_min']*100:.0f}% min")
                continue
            
            # Calculate annualized yield
            annualized_yield = (mid_price / strike) * (365 / max(1, days_to_exp)) * 100 if strike > 0 else 0
            
            # Determine play type based on delta and risk profile
            play_type = params['tag']
            
            # Add to filtered list with additional metrics
            opt.update({
                'mid_price': mid_price,
                'spread_pct': spread_pct * 100,  # Store as percentage
                'probability_itm': probability_itm * 100,  # Store as percentage
                'annualized_yield': annualized_yield,
                'days_to_expiration': days_to_exp,
                'play_type': play_type,
                'liquidity_score': min(100, (volume + open_interest) / 100),  # Simple liquidity score (0-100)
                'risk_tolerance': risk_tolerance.upper()
            })
            
            print(f"  ✓ ${strike} | {play_type} | Δ {delta:.2f} | "
                  f"${mid_price:.2f} | OI: {open_interest} | "
                  f"PoP: {probability_itm*100:.0f}% | Yield: {annualized_yield:.1f}%")
            
            filtered.append(opt)
            
        except Exception as e:
            print(f"  ⚠️  Error processing option: {str(e)}")
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
    Generate an enhanced markdown report with trading opportunities, simulations, and recommendations.
    
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
        "# 📊 Daily Options Trade Report",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
        "---"
    ]
    
    # Get current prices and prepare market data
    underlying_prices = {}
    tickers = set()
    
    for option in puts + calls:
        ticker = option.get('ticker')
        price = option.get('underlying_price')
        if ticker and price:
            underlying_prices[ticker] = price
            tickers.add(ticker)
    
    # --- Market Overview Section ---
    md_content.extend([
        "## 🌐 Market Overview",
        "### Key Indices (as of close)",
        "- **S&P 500 (SPY):** $XXX.XX (X.XX%) | 50D MA: $XXX.XX | 200D MA: $XXX.XX",
        "- **NASDAQ (QQQ):** $XXX.XX (X.XX%) | 50D MA: $XXX.XX | 200D MA: $XXX.XX",
        "- **VIX:** XX.XX (X.XX%) | 20D Avg: XX.XX",
        "\n### Market Sentiment",
        "- **Put/Call Ratio (5-day avg):** X.XX",
        "- **Market Trend:** [Bullish/Neutral/Bearish] based on [criteria]",
        "- **Sector Performance (Today): Tech +X.XX%, Financials +X.XX%, Healthcare +X.XX%"
    ])
    
    # --- Simulation Setup ---
    md_content.extend([
        "\n## 🔄 Simulation Parameters",
        f"- **Simulation Type:** {'Forward' if simulate_forward else 'Backtest'}",
        "- **Simulation Period:** 30 days",
        "- **Volatility Model:** GARCH(1,1)",
        "- **Monte Carlo Iterations:** 10,000"
    ])
    
    # Simulate top trades (top 5 of each)
    top_puts = puts[:5]
    top_calls = calls[:5]
    
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
    
    # --- Trade Recommendations ---
    md_content.extend(["\n## 🎯 Top Trade Recommendations"])
    
    # Add top 3 puts with detailed metrics
    for i, put in enumerate(puts[:3], 1):
        sim = put.get('simulation', {})
        md_content.extend([
            f"### {i}. {put.get('ticker', 'N/A')} - ${put.get('strike_price', 0):.2f} Put",
            "```",
            f"Entry:       ${put.get('underlying_price', 0):.2f}",
            f"Strike:      ${put.get('strike_price', 0):.2f} ({put.get('strike_pct_otm', 0):.1f}% OTM)",
            f"Premium:     ${put.get('mid_price', 0):.2f} (${put.get('bid', 0):.2f} / ${put.get('ask', 0):.2f})",
            f"Yield:       {put.get('premium_yield', 0):.1f}% ({put.get('annualized_yield', 0):.1f}% annualized)",
            f"Expiration:  {put.get('expiration', 'N/A')} (in {put.get('days_to_expiration', 0)} days)",
            f"Delta:       {put.get('delta', 0):.2f} | Gamma: {put.get('gamma', 0):.4f}",
            f"Theta:       ${put.get('theta', 0):.2f}/day | Vega: ${put.get('vega', 0):.2f}",
            f"Open Int:    {put.get('open_interest', 0):,} | Volume: {put.get('volume', 0):,}",
            "\n📊 Simulation Results:",
            f"- Expected P/L:   {sim.get('realized_yield', 0):.1f}%",
            f"- Max Drawdown:   {abs(sim.get('max_drawdown', 0)):.1f}%",
            f"- Prob. Profit:   {sim.get('probability_of_profit', 0):.1f}%",
            f"- Breakeven:      ${sim.get('breakeven', 0):.2f}",
            f"- Expected Exit:  ${sim.get('exit_price', 0):.2f} in {sim.get('held_days', 0)} days",
            "```",
            f"**Trade Rationale:** [Brief analysis of why this is a good trade]"
        ])
    
    # Add top 3 calls with detailed metrics
    for i, call in enumerate(calls[:3], 1):
        sim = call.get('simulation', {})
        md_content.extend([
            f"### {i+3}. {call.get('ticker', 'N/A')} - ${call.get('strike_price', 0):2f} Call",
            "```",
            f"Entry:       ${call.get('underlying_price', 0):.2f}",
            f"Strike:      ${call.get('strike_price', 0):.2f} ({call.get('strike_pct_otm', 0):.1f}% OTM)",
            f"Premium:     ${call.get('mid_price', 0):.2f} (${call.get('bid', 0):.2f} / ${call.get('ask', 0):.2f})",
            f"Yield:       {call.get('premium_yield', 0):.1f}% ({call.get('annualized_yield', 0):.1f}% annualized)",
            f"Expiration:  {call.get('expiration', 'N/A')} (in {call.get('days_to_expiration', 0)} days)",
            f"Delta:       {call.get('delta', 0):.2f} | Gamma: {call.get('gamma', 0):.4f}",
            f"Theta:       ${call.get('theta', 0):.2f}/day | Vega: ${call.get('vega', 0):.2f}",
            f"Open Int:    {call.get('open_interest', 0):,} | Volume: {call.get('volume', 0):,}",
            "\n📊 Simulation Results:",
            f"- Expected P/L:   {sim.get('realized_yield', 0):.1f}%",
            f"- Max Drawdown:   {abs(sim.get('max_drawdown', 0)):.1f}%",
            f"- Prob. Profit:   {sim.get('probability_of_profit', 0):.1f}%",
            f"- Breakeven:      ${sim.get('breakeven', 0):.2f}",
            f"- Expected Exit:  ${sim.get('exit_price', 0):.2f} in {sim.get('held_days', 0)} days",
            "```",
            f"**Trade Rationale:** [Brief analysis of why this is a good trade]"
        ])
    
    # --- Trade Lists ---
    # Add best puts table
    md_content.extend([
        "\n## 💰 Cash-Secured Puts (Top 10)",
        "| Ticker | Price | Strike | Premium | Yield | Annualized | DTE | Δ | POP% | Sim P/L% | Max DD% | Tags |",
        "|--------|-------|--------|---------|-------|------------|-----|---|------|----------|---------|------|"
    ])
    
    for put in puts[:10]:
        sim = put.get('simulation', {})
        tags = []
        if put.get('premium_yield', 0) > 3.0: tags.append("💰 High Yield")
        if sim.get('probability_of_profit', 0) > 70: tags.append("🎯 High Prob")
        if put.get('volume', 0) > 1000: tags.append("📈 High Volume")
        
        md_content.append(
            f"| {put.get('ticker', 'N/A')} "
            f"| ${put.get('underlying_price', 0):.2f} "
            f"| ${put.get('strike_price', 0):.2f} "
            f"| ${put.get('mid_price', 0):.2f} "
            f"| {put.get('premium_yield', 0):.1f}% "
            f"| {put.get('annualized_yield', 0):.1f}% "
            f"| {put.get('days_to_expiration', 0)} "
            f"| {put.get('delta', 0):.2f} "
            f"| {sim.get('probability_of_profit', 0):.1f}% "
            f"| {sim.get('realized_yield', 0):.1f}% "
            f"| {abs(sim.get('max_drawdown', 0)):.1f}% "
            f"| {' '.join(tags)} |"
        )
    
    # Add best calls table
    md_content.extend([
        "\n## 📈 Covered Calls (Top 10)",
        "| Ticker | Price | Strike | Premium | Yield | Annualized | DTE | Δ | POP% | Sim P/L% | Max DD% | Tags |",
        "|--------|-------|--------|---------|-------|------------|-----|---|------|----------|---------|------|"
    ])
    
    for call in calls[:10]:
        sim = call.get('simulation', {})
        tags = []
        if call.get('premium_yield', 0) > 2.0: tags.append("💰 High Yield")
        if sim.get('probability_of_profit', 0) > 70: tags.append("🎯 High Prob")
        if call.get('volume', 0) > 1000: tags.append("📈 High Volume")
        
        md_content.append(
            f"| {call.get('ticker', 'N/A')} "
            f"| ${call.get('underlying_price', 0):.2f} "
            f"| ${call.get('strike_price', 0):.2f} "
            f"| ${call.get('mid_price', 0):.2f} "
            f"| {call.get('premium_yield', 0):.1f}% "
            f"| {call.get('annualized_yield', 0):.1f}% "
            f"| {call.get('days_to_expiration', 0)} "
            f"| {call.get('delta', 0):.2f} "
            f"| {sim.get('probability_of_profit', 0):.1f}% "
            f"| {sim.get('realized_yield', 0):.1f}% "
            f"| {abs(sim.get('max_drawdown', 0)):.1f}% "
            f"| {' '.join(tags)} |"
        )
    
    # --- Trade Execution ---
    md_content.extend([
        "\n## 🛠️ Trade Execution",
        "### Suggested Position Sizing",
        "- **Account Size:** $XX,XXX",
        "- **Max Risk per Trade:** X% of portfolio",
        "- **Position Size:** X contracts (max risk: $XXX)",
        "\n### Entry/Exit Rules",
        "- **Entry:** Limit order at mid-price or better",
        "- **Stop Loss:** -XX% of premium received",
        "- **Profit Target:** XX% of max profit",
        "- **Management:** Consider rolling at XX DTE or XX% of max profit"
    ])
    
    # --- Risk Management ---
    md_content.extend([
        "\n## ⚠️ Risk Management",
        "### Portfolio Allocation",
        "- Max X% of portfolio in any single underlying",
        "- Max X% in any single sector",
        "- Max X% in any single strategy",
        "\n### Risk Metrics",
        "- Portfolio Beta: X.XX",
        "- Portfolio Theta: $XX.XX/day",
        "- Portfolio Delta: $X,XXX per 1% move",
        "- Portfolio Vega: $XX.XX per 1 volatility point"
    ])
    
    # --- Market Data & Analysis ---
    md_content.extend([
        "\n## 📊 Market Data & Analysis",
        "### Implied vs Historical Volatility",
        "- **IV Percentile:** XX% (Xth percentile)",
        "- **IV Rank:** XX (X/100)",
        "- **Current IV/HV Ratio:** X.XX",
        "\n### Technical Analysis",
        "- **Trend:** [Up/Down/Sideways]",
        "- **Key Levels:** Support at $XX.XX, Resistance at $XX.XX",
        "- **RSI(14):** XX.X (Oversold/Overbought/Neutral)",
        "- **MACD:** [Bullish/Bearish] crossover"
    ])
    
    # --- Economic Calendar ---
    md_content.extend([
        "\n## 📅 Upcoming Events",
        "| Date | Time (ET) | Event | Impact |",
        "|------|----------|-------|--------|",
        "| Tues, Jun 10 | 8:30 AM | CPI m/m | 🟡 Medium |",
        "| Wed, Jun 11 | 2:00 PM | FOMC Statement | 🔴 High |",
        "| Thu, Jun 12 | 8:30 AM | Initial Claims | 🟢 Low |"
    ])
    
    # --- Notes & Disclaimers ---
    md_content.extend([
        "\n## 📝 Notes & Disclaimers",
        "### Key Assumptions",
        "- Options pricing uses mid-point between bid/ask",
        "- Greeks calculated using Black-Scholes model",
        "- Simulation uses historical volatility and Monte Carlo methods",
        "- No transaction costs or slippage included in simulations",
        "\n### Risk Disclosure",
        "⚠️ **Options trading involves substantial risk of loss and is not suitable for all investors.**",
        "- Past performance is not indicative of future results",
        "- Simulated results do not reflect actual trading and may not account for all risks",
        "- Consider your risk tolerance and investment objectives before trading",
        "\n### Data Sources",
        "- Market data provided by Polygon.io",
        f"- Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Simulation mode: {'Forward' if simulate_forward else 'Backtest'}"
    ])
    
    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(line for line in md_content if line is not None))
    
    print(f"✅ Report generated: {filename}")
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

def get_available_expirations(ticker, current_price, max_retries=3):
    """
    Get available expiration dates for a given ticker.
    
    Args:
        ticker: Stock ticker symbol
        current_price: Current stock price
        max_retries: Maximum number of retry attempts
        
    Returns:
        List of available expiration dates (YYYY-MM-DD)
    """
    print(f"\n📅 Fetching available expiration dates for {ticker}...")
    
    # First, try to get options contracts to see available expirations
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        'underlying_ticker': ticker,
        'limit': 1000,
        'expired': 'false',
        'apiKey': API_KEY
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'results' in data and data['results']:
                # Extract unique expiration dates
                expirations = sorted(list(set([
                    result['expiration_date'] 
                    for result in data['results']
                    if 'expiration_date' in result
                ])))
                
                if expirations:
                    print(f"  Found {len(expirations)} expiration dates for {ticker}")
                    return expirations
                
            print(f"  No expiration dates found for {ticker} (attempt {attempt + 1}/{max_retries})")
            
        except Exception as e:
            print(f"  Error fetching expirations for {ticker}: {str(e)}")
        
        if attempt < max_retries - 1:
            wait_time = (2 ** attempt) * 2  # Exponential backoff
            print(f"  Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    print(f"  ⚠️ Using default expiration date: {TARGET_EXPIRATION}")
    return [TARGET_EXPIRATION]

def select_best_expiration(expirations, min_dte=10, max_dte=45):
    """
    Select the best expiration date based on DTE range.
    
    Args:
        expirations: List of expiration dates (YYYY-MM-DD)
        min_dte: Minimum days to expiration
        max_dte: Maximum days to expiration
        
    Returns:
        Selected expiration date (YYYY-MM-DD)
    """
    if not expirations:
        return TARGET_EXPIRATION
    
    today = date.today()
    valid_expirations = []
    
    for exp_date_str in expirations:
        try:
            exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d').date()
            dte = (exp_date - today).days
            if min_dte <= dte <= max_dte:
                valid_expirations.append((exp_date_str, dte))
        except (ValueError, TypeError):
            continue
    
    if not valid_expirations:
        print(f"  No valid expirations found in {min_dte}-{max_dte} DTE range, using closest")
        # Find the closest expiration to our target DTE
        target_dte = (min_dte + max_dte) // 2
        return min(
            [(d, abs((datetime.strptime(d, '%Y-%m-%d').date() - today).days - target_dte)) 
             for d in expirations],
            key=lambda x: x[1]
        )[0]
    
    # Sort by DTE closest to our target range
    target_dte = (min_dte + max_dte) // 2
    best_exp = min(valid_expirations, key=lambda x: abs(x[1] - target_dte))
    
    print(f"  Selected expiration: {best_exp[0]} ({best_exp[1]} DTE)")
    return best_exp[0]

def run(risk_tolerance: str = 'medium'):
    """
    Main function to run the options scanner.
    
    Args:
        risk_tolerance: Risk tolerance level ('low', 'medium', 'high')
    """
    # Declare global variables at the beginning of the function
    global TARGET_EXPIRATION, TICKERS, MIN_PREMIUM, MIN_DELTA, MAX_DELTA, MIN_OPEN_INTEREST
    
    # Validate risk tolerance
    risk_tolerance = risk_tolerance.lower()
    if risk_tolerance not in ['low', 'medium', 'high']:
        print(f"⚠️  Invalid risk tolerance: {risk_tolerance}. Defaulting to 'medium'.")
        risk_tolerance = 'medium'
    
    print("🚀 Starting Polygon Options Scanner" + " " * 20)
    print("="*80)
    print(f"📅 Scan started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Tickers to scan: {', '.join(TICKERS)}")
    print(f"🎯 Risk tolerance: {risk_tolerance.upper()}")
    print("-"*80 + "\n")
    
    # Initialize statistics
    stats = {
        'start_time': datetime.now(),
        'tickers_processed': 0,
        'tickers_with_puts': 0,
        'tickers_with_calls': 0,
        'total_puts_found': 0,
        'total_calls_found': 0,
        'tickers_with_errors': 0,
        'errors': [],
        'risk_tolerance': risk_tolerance
    }
    
    # Initialize markdown content
    md_content = [
        "# 📊 Options Scan Report",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Tickers Scanned:** {len(TICKERS)}",
        f"**Risk Tolerance:** {risk_tolerance.upper()}",
        ""
    ]
    
    # Check market status
    try:
        market_status = get_market_status()
        md_content.append(f"**Market Status:** {market_status}")
        if market_status != 'open':
            md_content.append("⚠️ **Warning:** Market is not currently open. Data may be stale.")
    except Exception as e:
        md_content.append(f"⚠️ **Warning:** Could not determine market status: {str(e)}")
    
    md_content.extend(["", "## 📋 Scan Results", ""])
    
    # Initialize lists to store all puts and calls for summary
    all_puts = []
    all_calls = []
    
    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'output/trade_ideas_{risk_tolerance}_{timestamp}.md'
    
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
    
    # Process each ticker with rate limiting
    for i, ticker in enumerate(TICKERS, 1):
        # Add random delay between tickers to avoid rate limiting
        if i > 1:  # No delay before first ticker
            delay = 0.5 + random.uniform(0, 1.0)  # 0.5-1.5 second delay
            time.sleep(delay)
        
        ticker_start = datetime.now()
        stats['tickers_processed'] += 1
        ticker_status = ""
        ticker_error = ""
        puts_found = 0
        calls_found = 0
        price = None
        options_chain = None
        selected_expiration = TARGET_EXPIRATION  # Default to global target
        
        print(f"\n{'='*80}\n📊 [{i}/{len(TICKERS)}] Analyzing {ticker} (Risk: {risk_tolerance.upper()})")
        print("-"*80)
        
        try:
            # Get stock price with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"🔍 Fetching current price for {ticker} (attempt {attempt + 1}/{max_retries})...")
                    price = get_stock_price(ticker)
                    if not price or price <= 0:
                        raise ValueError(f"Invalid price ${price:.2f} for {ticker}")
                    print(f"✅ Current price: ${price:.2f}")
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"⚠️  Error fetching price: {str(e)}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
            
            # Get available expirations and select the best one
            try:
                print("\n📅 Fetching available option expirations...")
                expirations = get_available_expirations(ticker, price)
                selected_expiration = select_best_expiration(expirations, min_dte=10, max_dte=45)
                print(f"🎯 Selected expiration: {selected_expiration}")
                
                # Update the global TARGET_EXPIRATION for this ticker
                TARGET_EXPIRATION = selected_expiration
                
            except Exception as e:
                print(f"⚠️  Error selecting expiration date: {str(e)}")
                print(f"⚠️  Using default expiration: {TARGET_EXPIRATION}")
            
            # ... (rest of the code remains the same)
            # Get options chain with progress indication and error handling
            print(f"\n🔍 Fetching options chain for {ticker} (Exp: {TARGET_EXPIRATION})...")
            
            # First get puts
            print(f"📉 Fetching PUT options...")
            try:
                puts_chain = get_options_chain(ticker, 'put', price)
                if not puts_chain or 'results' not in puts_chain or not puts_chain['results']:
                    print("⚠️  No PUT options data available")
                    puts_chain = {'results': []}
                else:
                    print(f"✅ Found {len(puts_chain['results'])} PUT contracts")
                    # Filter for selected expiration only
                    puts_chain['results'] = [opt for opt in puts_chain['results'] 
                                          if opt.get('expiration_date') == TARGET_EXPIRATION]
                    print(f"   → {len(puts_chain['results'])} contracts for {TARGET_EXPIRATION}")
            except Exception as e:
                print(f"⚠️  Error fetching PUT options: {str(e)}")
                puts_chain = {'results': []}
            
            # Then get calls
            print(f"📈 Fetching CALL options...")
            try:
                calls_chain = get_options_chain(ticker, 'call', price)
                if not calls_chain or 'results' not in calls_chain or not calls_chain['results']:
                    print("⚠️  No CALL options data available")
                    calls_chain = {'results': []}
                else:
                    print(f"✅ Found {len(calls_chain['results'])} CALL contracts")
                    # Filter for selected expiration only
                    calls_chain['results'] = [opt for opt in calls_chain['results'] 
                                           if opt.get('expiration_date') == TARGET_EXPIRATION]
                    print(f"   → {len(calls_chain['results'])} contracts for {TARGET_EXPIRATION}")
            except Exception as e:
                print(f"⚠️  Error fetching CALL options: {str(e)}")
                calls_chain = {'results': []}
            
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
                if 'puts' in options_chain and options_chain['puts']:
                    puts_filtered = filter_and_sort_options(
                        options_chain['puts'], 
                        price, 
                        is_put=True,
                        risk_tolerance=risk_tolerance
                    )
                    puts_found = len(puts_filtered)
                    stats['total_puts_found'] += puts_found
                    if puts_found > 0:
                        stats['tickers_with_puts'] += 1
                
                    # Add to all_puts for summary
                    for put in puts_filtered:
                        put.update({
                            'ticker': ticker,
                            'current_price': price,
                            'expiration': TARGET_EXPIRATION
                        })
                        all_puts.append(put)
            
                # Process calls with risk tolerance
                if 'calls' in options_chain and options_chain['calls']:
                    calls_filtered = filter_and_sort_options(
                        options_chain['calls'], 
                        price, 
                        is_put=False,
                        risk_tolerance=risk_tolerance
                    )
                    calls_found = len(calls_filtered)
                    stats['total_calls_found'] += calls_found
                    if calls_found > 0:
                        stats['tickers_with_calls'] += 1
                    
                    # Add to all_calls for summary
                    for call in calls_filtered:
                        call.update({
                            'ticker': ticker,
                            'current_price': price,
                            'expiration': TARGET_EXPIRATION
                        })
                        all_calls.append(call)
                
                if not puts_filtered and not calls_filtered:
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
    end_time = datetime.now()
    total_runtime = end_time - stats['start_time']
    
    # Calculate success rate
    success_rate = ((stats['tickers_processed'] - stats['tickers_with_errors']) / 
                   stats['tickers_processed'] * 100) if stats['tickers_processed'] > 0 else 0
    
    # Add summary to markdown
    md_content.extend([
        "\n## 📊 Scan Summary",
        "### 📈 Statistics",
        f"- **Total tickers processed:** {stats['tickers_processed']}",
        f"- **Tickers with qualifying puts:** {stats['tickers_with_puts']} ({stats['tickers_with_puts']/stats['tickers_processed']*100:.1f}%)",
        f"- **Tickers with qualifying calls:** {stats['tickers_with_calls']} ({stats['tickers_with_calls']/stats['tickers_processed']*100:.1f}%)",
        f"- **Total puts found:** {stats['total_puts_found']}",
        f"- **Total calls found:** {stats['total_calls_found']}",
        f"- **Scan success rate:** {success_rate:.1f}%",
        f"- **Tickers with errors:** {stats['tickers_with_errors']}",
        f"- **Scan start time:** {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Scan end time:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Total runtime:** {total_runtime}",
        "",
        "### ⚙️ Scan Parameters",
        f"- **Target expiration date:** {TARGET_EXPIRATION}",
        f"- **Delta range:** {MIN_DELTA:.2f} - {MAX_DELTA:.2f}",
        f"- **Minimum premium:** ${MIN_PREMIUM:.2f}",
        f"- **Minimum open interest:** {MIN_OPEN_INTEREST}",
        f"- **Strike price range for puts:** {MIN_STRIKE_PCT*100:.1f}% - 100% of current price",
        f"- **Strike price range for calls:** 100% - {MAX_STRIKE_PCT*100:.1f}% of current price",
        "",
        "### 🔍 Top Trades by Annualized Yield"
    ])
    
    # Print summary to console
    print("\n" + "="*80)
    print("📊 SCAN COMPLETE - SUMMARY")
    print("="*80)
    print(f"✅ Processed {stats['tickers_processed']} tickers in {total_runtime}")
    print(f"📊 Found {stats['total_puts_found']} puts and {stats['total_calls_found']} calls meeting criteria")
    print(f"📈 Success rate: {success_rate:.1f}%")
    
    if stats['tickers_with_errors'] > 0:
        print(f"\n⚠️  Encountered {stats['tickers_with_errors']} errors:")
        for i, error in enumerate(stats['errors'][:5], 1):  # Show first 5 errors
            print(f"   {i}. {error}")
        if len(stats['errors']) > 5:
            print(f"   ... and {len(stats['errors']) - 5} more errors")
    
    print("\n🔍 Scan results saved to:")
    print(f"   - Detailed report: {output_file}")
    
    if all_puts or all_calls:
        print("\n🏆 Top Trades:")
        # Show top 3 puts and calls if available
        if all_puts:
            print("\n📉 Top 3 Puts by Annualized Yield:")
            for i, put in enumerate(sorted(all_puts, key=lambda x: x.get('annualized_yield', 0), reverse=True)[:3], 1):
                print(f"   {i}. {put.get('ticker')} ${put.get('strike_price'):.2f} Put | "
                      f"Premium: ${put.get('mid_price', 0):.2f} | "
                      f"Yield: {put.get('annualized_yield', 0):.1f}% | "
                      f"Δ {put.get('delta', 0):.2f} | "
                      f"DTE: {put.get('days_to_expiration', 0)}")
        
        if all_calls:
            print("\n📈 Top 3 Calls by Annualized Yield:")
            for i, call in enumerate(sorted(all_calls, key=lambda x: x.get('annualized_yield', 0), reverse=True)[:3], 1):
                print(f"   {i}. {call.get('ticker')} ${call.get('strike_price'):.2f} Call | "
                      f"Premium: ${call.get('mid_price', 0):.2f} | "
                      f"Yield: {call.get('annualized_yield', 0):.1f}% | "
                      f"Δ {call.get('delta', 0):.2f} | "
                      f"DTE: {call.get('days_to_expiration', 0)}")
    
    print("\n" + "="*80)
    
    # Helper function to generate trade rationale
    def generate_rationale(opt, is_put):
        ticker = opt.get('ticker', 'UNKNOWN')
        strike = opt.get('strike_price', 0)
        current_price = opt.get('current_price', 0)
        premium = opt.get('mid_price', 0)
        dte = opt.get('days_to_expiration', 0)
        delta = opt.get('delta', 0)
        pop = opt.get('probability_itm', 0) / 100  # Convert back to decimal
        
        # Determine if ITM/OTM
        if is_put:
            moneyness = "ITM" if strike > current_price else "OTM"
            breakeven = strike - premium
            max_profit = premium
            max_loss = strike - premium
        else:  # call
            moneyness = "ITM" if strike < current_price else "OTM"
            breakeven = strike + premium
            max_profit = "Unlimited" if is_put else "Unlimited"
            max_loss = premium
        
        # Generate rationale based on option metrics
        rationale = []
        
        # Play type and risk profile
        rationale.append(f"**{opt.get('play_type', 'Trade')}** ({opt.get('risk_tolerance', 'MEDIUM')} risk): ")
        
        # Basic trade setup
        if is_put:
            rationale.append(f"Sell ${strike:.2f} put ({moneyness}) "
                           f"for ${premium:.2f} premium, {dte} DTE.")
        else:
            rationale.append(f"Sell ${strike:.2f} call ({moneyness}) "
                           f"for ${premium:.2f} premium, {dte} DTE.")
        
        # Key metrics
        rationale.append(f"\n- **Probability of Profit (PoP):** {pop*100:.0f}%")
        rationale.append(f"- **Annualized Yield:** {opt.get('annualized_yield', 0):.1f}%")
        rationale.append(f"- **Delta:** {delta:.2f}")
        rationale.append(f"- **Breakeven:** ${breakeven:.2f}")
        
        # Risk/Reward
        rationale.append("\n**Risk/Reward:**")
        rationale.append(f"- Max Profit: ${max_profit:.2f} per contract")
        rationale.append(f"- Max Loss: ${max_loss:.2f} per contract" if isinstance(max_loss, (int, float)) else f"- Max Loss: {max_loss} (naked call)")
        
        # Liquidity note
        if opt.get('liquidity_score', 0) < 20:
            rationale.append("\n⚠️ **Liquidity Warning:** Low open interest/volume - consider smaller position size.")
        
        return "\n".join(rationale)
    
    # Add top puts with rationales
    if all_puts:
        md_content.extend([
            "\n## 📉 Top Put Opportunities",
            "| Ticker | Strike | Premium | Yield | DTE | Δ | PoP | Play Type |",
            "|--------|--------|---------|-------|-----|---|-----|-----------|"
        ])
        
        # Sort by yield descending and take top 10
        top_puts = sorted(all_puts, key=lambda x: x.get('annualized_yield', 0), reverse=True)[:10]
        for put in top_puts:
            md_content.append(
                f"| {put.get('ticker')} | "
                f"${put.get('strike_price'):.2f} | "
                f"${put.get('mid_price', 0):.2f} | "
                f"{put.get('annualized_yield', 0):.1f}% | "
                f"{put.get('days_to_expiration', 0)} | "
                f"{put.get('delta', 0):.2f} | "
                f"{put.get('probability_itm', 0):.0f}% | "
                f"{put.get('play_type', 'N/A')} |"
            )
            
            # Add rationale as collapsible section
            rationale = generate_rationale(put, is_put=True)
            md_content.append(f"\n<details><summary>📝 <b>Trade Rationale</b></summary>\n\n{rationale}\n</details>\n")
    
    # Add top calls with rationales
    if all_calls:
        md_content.extend([
            "\n## 📈 Top Call Opportunities",
            "| Ticker | Strike | Premium | Yield | DTE | Δ | PoP | Play Type |",
            "|--------|--------|---------|-------|-----|---|-----|-----------|"
        ])
        
        # Sort by yield descending and take top 10
        top_calls = sorted(all_calls, key=lambda x: x.get('annualized_yield', 0), reverse=True)[:10]
        for call in top_calls:
            md_content.append(
                f"| {call.get('ticker')} | "
                f"${call.get('strike_price'):.2f} | "
                f"${call.get('mid_price', 0):.2f} | "
                f"{call.get('annualized_yield', 0):.1f}% | "
                f"{call.get('days_to_expiration', 0)} | "
                f"{call.get('delta', 0):.2f} | "
                f"{call.get('probability_itm', 0):.0f}% | "
                f"{call.get('play_type', 'N/A')} |"
            )
            
            # Add rationale as collapsible section
            rationale = generate_rationale(call, is_put=False)
            md_content.append(f"\n<details><summary>📝 <b>Trade Rationale</b></summary>\n\n{rationale}\n</details>\n")
    
    # Add error section if any errors occurred
    if stats['errors']:
        md_content.extend([
            "\n## ❌ Errors Encountered",
            "The following errors were encountered during processing:",
            ""
        ])
        
        for error in stats['errors']:
            md_content.append(f"- {error}")
    
    # Add footer
    md_content.extend([
        "",
        "---",
        f"Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S %Z')}",
        f"Total runtime: {datetime.now() - stats['start_time']}"
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

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Options Scanner with Polygon.io')
    parser.add_argument('--risk', type=str, default='medium',
                      choices=['low', 'medium', 'high'],
                      help='Risk tolerance level (default: medium)')
    parser.add_argument('--tickers', type=str, nargs='+',
                      help='List of tickers to scan (space-separated)')
    parser.add_argument('--min-premium', type=float, default=DEFAULT_MIN_PREMIUM,
                      help=f'Minimum premium (default: {DEFAULT_MIN_PREMIUM})')
    parser.add_argument('--min-delta', type=float, default=DEFAULT_MIN_DELTA,
                      help=f'Minimum delta (default: {DEFAULT_MIN_DELTA})')
    parser.add_argument('--max-delta', type=float, default=DEFAULT_MAX_DELTA,
                      help=f'Maximum delta (default: {DEFAULT_MAX_DELTA})')
    parser.add_argument('--min-oi', type=int, default=DEFAULT_MIN_OPEN_INTEREST,
                      help=f'Minimum open interest (default: {DEFAULT_MIN_OPEN_INTEREST})')
    return parser.parse_args()

def main():
    """Main entry point for the script."""
    try:
        args = parse_args()
        
        # Update global config if provided
        if args.tickers:
            global TICKERS
            TICKERS = [t.upper() for t in args.tickers]
        
        # Update other globals from args
        global MIN_PREMIUM, MIN_DELTA, MAX_DELTA, MIN_OPEN_INTEREST
        MIN_PREMIUM = args.min_premium
        MIN_DELTA = args.min_delta
        MAX_DELTA = args.max_delta
        MIN_OPEN_INTEREST = args.min_oi
        
        print(f"🔍 Starting scan with risk tolerance: {args.risk.upper()}")
        print(f"📊 Tickers: {', '.join(TICKERS) if args.tickers else 'Default list'}")
        print(f"⚙️  Parameters: Premium>${MIN_PREMIUM:.2f}, Δ={MIN_DELTA:.2f}-{MAX_DELTA:.2f}, OI>={MIN_OPEN_INTEREST}")
        
        # Run with specified risk tolerance
        run(risk_tolerance=args.risk)
        
    except KeyboardInterrupt:
        print("\n⚠️  Scan interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import argparse
    main()
