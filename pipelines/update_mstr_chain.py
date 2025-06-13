#!/usr/bin/env python3
"""
MSTR Option Chain Updater

This script fetches the latest option chain data for MSTR and saves it to a parquet file.
It's designed to be run as a scheduled job (e.g., via cron or GitHub Actions).
"""
import os
import sys
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('update_chain.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
SYMBOL = 'MSTR'
OUTPUT_DIR = Path('data/option_chains')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def fetch_option_chain(symbol: str, expiration: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch option chain data from data source.
    
    Args:
        symbol: The underlying symbol (e.g., 'MSTR')
        expiration: Optional expiration date in YYYY-MM-DD format
        
    Returns:
        DataFrame containing option chain data
    """
    logger.info(f"Fetching option chain for {symbol}" + 
               (f" (expiry: {expiration})" if expiration else ""))
    
    # In a real implementation, this would call your data provider's API
    # For example, using Polygon.io, TD Ameritrade, or Interactive Brokers
    
    # Mock implementation - replace with actual API call
    try:
        # This is a placeholder - implement actual API call
        # Example with Polygon.io:
        # from polygon import RESTClient
        # client = RESTClient(api_key=os.getenv('POLYGON_API_KEY'))
        # options = []
        # for o in client.list_options_contracts(
        #     underlying_ticker=symbol,
        #     expired=False,
        #     expiration_date=expiration,
        #     limit=1000
        # ):
        #     options.append(vars(o))
        # df = pd.DataFrame(options)
        
        # For now, return an empty DataFrame with expected columns
        df = pd.DataFrame(columns=[
            'symbol', 'strike_price', 'expiration_date', 'option_type',
            'last_price', 'bid', 'ask', 'volume', 'open_interest',
            'implied_volatility', 'delta', 'gamma', 'theta', 'vega',
            'last_trade_timestamp', 'underlying_price'
        ])
        
        logger.info(f"Retrieved {len(df)} options")
        return df
        
    except Exception as e:
        logger.error(f"Error fetching option chain: {e}", exc_info=True)
        return pd.DataFrame()

def find_next_expirations(lookahead_weeks: int = 4) -> List[str]:
    """
    Find the next N weekly expirations.
    
    Args:
        lookahead_weeks: Number of weeks to look ahead
        
    Returns:
        List of expiration dates in YYYY-MM-DD format
    """
    # In a real implementation, this would query the exchange calendar
    # For now, we'll generate the next N Fridays
    
    today = datetime.today()
    fridays = []
    
    # Find the next Friday
    days_ahead = 4 - today.weekday()  # 4 = Friday (0 = Monday)
    if days_ahead <= 0:  # If today is Friday or after
        days_ahead += 7
    next_friday = today + timedelta(days=days_ahead)
    
    # Add the next N Fridays
    for i in range(lookahead_weeks):
        friday = next_friday + timedelta(weeks=i)
        fridays.append(friday.strftime('%Y-%m-%d'))
    
    return fridays

def save_chain_to_parquet(df: pd.DataFrame, symbol: str, expiration: str) -> str:
    """
    Save option chain data to a parquet file.
    
    Args:
        df: DataFrame containing option chain data
        symbol: Underlying symbol
        expiration: Expiration date in YYYY-MM-DD format
        
    Returns:
        Path to the saved file
    """
    if df.empty:
        logger.warning("No data to save")
        return ""
    
    # Create output directory if it doesn't exist
    output_dir = OUTPUT_DIR / symbol
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    date_str = datetime.today().strftime('%Y%m%d')
    filename = f"{symbol}_{expiration.replace('-', '')}_{date_str}.parquet"
    filepath = output_dir / filename
    
    # Save to parquet
    df.to_parquet(filepath, index=False)
    logger.info(f"Saved {len(df)} options to {filepath}")
    
    return str(filepath)

def update_option_chains():
    """Main function to update option chains."""
    logger.info("Starting option chain update")
    
    # Find next expirations
    expirations = find_next_expirations(lookahead_weeks=4)
    
    # Track updated files
    updated_files = []
    
    # Fetch and save chains for each expiration
    for expiry in expirations:
        try:
            # Fetch chain data
            df = fetch_option_chain(SYMBOL, expiry)
            
            if not df.empty:
                # Save to parquet
                filepath = save_chain_to_parquet(df, SYMBOL, expiry)
                if filepath:
                    updated_files.append(filepath)
            else:
                logger.warning(f"No data returned for {SYMBOL} {expiry}")
                
        except Exception as e:
            logger.error(f"Error processing {SYMBOL} {expiry}: {e}", exc_info=True)
    
    # Update manifest file
    update_manifest(updated_files)
    
    logger.info(f"Option chain update complete. Updated {len(updated_files)} files.")

def update_manifest(updated_files: List[str]):
    """Update manifest file with latest chain files."""
    manifest_path = OUTPUT_DIR / 'manifest.json'
    
    try:
        # Load existing manifest
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        else:
            manifest = {
                'last_updated': datetime.utcnow().isoformat(),
                'files': []
            }
        
        # Update with new files
        existing_files = set(manifest['files'])
        new_files = [f for f in updated_files if f not in existing_files]
        
        if new_files:
            manifest['files'].extend(new_files)
            manifest['last_updated'] = datetime.utcnow().isoformat()
            
            # Save updated manifest
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            logger.info(f"Updated manifest with {len(new_files)} new files")
            
    except Exception as e:
        logger.error(f"Error updating manifest: {e}", exc_info=True)

def main():
    """Main entry point."""
    try:
        update_option_chains()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
