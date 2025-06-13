"""Helper functions for interacting with Polygon.io API."""
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
import requests
from polygon import RESTClient


def list_contracts(
    underlying: str, 
    expiration_date: str, 
    client: RESTClient
) -> List[Dict]:
    """List all option contracts for a given underlying and expiration date.
    
    Args:
        underlying: The underlying ticker symbol (e.g., 'MSTR')
        expiration_date: Expiration date in 'YYYY-MM-DD' format
        client: Authenticated Polygon RESTClient
        
    Returns:
        List of contract dictionaries
    """
    try:
        contracts = client.get_reference_options_contracts(
            underlying_ticker=underlying.upper(),
            expiration_date=expiration_date,
            limit=1000
        )
        return contracts.results if hasattr(contracts, 'results') else []
    except Exception as e:
        print(f"Error listing contracts: {str(e)}")
        return []


def fetch_iv_snapshot(
    contract_ticker: str, 
    as_of: str, 
    client: RESTClient,
    max_retries: int = 1,
    retry_delay: float = 0.2
) -> Dict:
    """Fetch IV snapshot for a specific option contract with retry logic.
    
    Args:
        contract_ticker: Full contract ticker (e.g., 'O:MSTR250612C00405000')
        as_of: Date in 'YYYY-MM-DD' format
        client: Authenticated Polygon RESTClient
        max_retries: Maximum number of retry attempts (default: 1)
        retry_delay: Delay between retries in seconds (default: 0.2s)
        
    Returns:
        Dictionary containing snapshot data with implied volatility
        
    Raises:
        ValueError: If IV data is missing after all retries
        Exception: For other API errors after all retries
    "
        
    Raises:
        ValueError: If IV data is missing after retries or contract ticker is invalid
        Exception: For other errors after all retries are exhausted
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            # Get the snapshot for the specific contract
            snapshot = client.get_snapshot_option_contract(
                underlying_asset=contract_ticker,
                option_contract=contract_ticker,
                as_of=as_of
            )
            
            # Check if we got valid data
            if not hasattr(snapshot, 'implied_volatility') or snapshot.implied_volatility is None:
                if attempt < max_retries:
                    import time
                    time.sleep(retry_delay)
                    continue
                raise ValueError(f"IV missing for {contract_ticker} on {as_of}")
            
            # If we get here, we have valid data
            return {
                'implied_volatility': snapshot.implied_volatility,
                'delta': getattr(snapshot, 'delta', None),
                'gamma': getattr(snapshot, 'gamma', None),
                'theta': getattr(snapshot, 'theta', None),
                'vega': getattr(snapshot, 'vega', None),
                'open_interest': getattr(snapshot, 'open_interest', None),
                'volume': getattr(snapshot, 'volume', None),
                'bid': getattr(snapshot, 'bid', None),
                'ask': getattr(snapshot, 'ask', None),
                'last_trade': getattr(snapshot, 'last_trade', None)
            }
            
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                import time
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            
            # If we've exhausted all retries, raise the last exception
            if 'IV missing' in str(e):
                raise ValueError(f"IV missing for {contract_ticker} on {as_of}")
            raise Exception(f"Failed to fetch IV for {contract_ticker} after {max_retries + 1} attempts: {str(e)}")
    
    # This should never be reached due to the raises above, but just in case
    raise ValueError(f"Failed to fetch IV for {contract_ticker} on {as_of} after {max_retries + 1} attempts")


def get_stock_price(ticker: str, date: str, api_key: str) -> Optional[float]:
    """Get the closing price of a stock on a specific date.
    
    Args:
        ticker: Stock ticker symbol
        date: Date in 'YYYY-MM-DD' format
        api_key: Polygon.io API key
        
    Returns:
        Closing price or None if not found
    """
    url = f"https://api.polygon.io/v1/open-close/{ticker.upper()}/{date}"
    params = {"adjusted": "true", "apiKey": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('close')
    except Exception as e:
        print(f"Error getting stock price: {str(e)}")
        return None


def find_atm_contracts(
    contracts: List[Dict], 
    stock_price: float
) -> Tuple[Optional[str], Optional[str]]:
    """Find ATM call and put contracts from a list of contracts.
    
    Args:
        contracts: List of contract dictionaries
        stock_price: Current stock price
        
    Returns:
        Tuple of (call_ticker, put_ticker) or (None, None) if not found
    """
    if not contracts:
        return None, None
    
    calls = [c for c in contracts if c.get('contract_type') == 'call']
    puts = [c for c in contracts if c.get('contract_type') == 'put']
    
    # Sort by distance from ATM
    calls.sort(key=lambda x: abs(x.get('strike_price', float('inf')) - stock_price))
    puts.sort(key=lambda x: abs(x.get('strike_price', float('inf')) - stock_price))
    
    return (
        calls[0]['ticker'] if calls else None, 
        puts[0]['ticker'] if puts else None
    )
