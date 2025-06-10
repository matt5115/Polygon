"""
Test script for submitting a futures order to Ironbeam's demo environment.
"""
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to import client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from client.ironbeam import IronbeamClient

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize the Ironbeam client
    client = IronbeamClient()
    
    # Define test order parameters
    symbol = "ESU5"  # E-mini S&P 500, Sept 2025
    quantity = 1
    order_type = "MARKET"
    side = "BUY"
    
    print(f"Placing {order_type} order to {side} {quantity} {symbol}...")
    
    try:
        # Submit the order
        response = client.submit_futures_order(
            symbol=symbol,
            quantity=quantity,
            order_type=order_type,
            side=side
        )
        
        print("\n✅ Order submitted successfully!")
        print("Response:", response)
        
    except Exception as e:
        print(f"\n❌ Error submitting order: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
