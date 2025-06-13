# Options IV Snapshot Utility

This utility fetches and analyzes option implied volatility (IV) data from Polygon.io for a given stock and date.

## Features

- Fetch ATM (At-The-Money) call and put options for a given expiration
- Retrieve IV snapshots for specific contracts
- Calculate IV skew (Put IV - Call IV)
- Support for historical data analysis

## Prerequisites

- Python 3.8+
- Polygon.io API key (Starter plan or higher)
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your Polygon.io API key:
   ```bash
   cp .env.example .env
   ```

## Usage

1. Run the script:
   ```bash
   python option_iv_snapshot.py
   ```

2. By default, it will fetch data for MSTR as of 30 days ago. To customize:
   - Edit the `ticker`, `target_date`, and `expiration_date` variables in `option_iv_snapshot.py`

## Example Output

```
Fetching data for MSTR on 2025-05-12...
MSTR price on 2025-05-12: $404.90

Fetching option contracts expiring on 2025-06-13...
Found 10 contracts

ATM Call: O:MSTR250613C00405000
ATM Put:  O:MSTR250613P00405000

Fetching IV snapshots for 2025-05-12...

ATM Call IV: 9.6%
ATM Put IV:  8.9%
IV Skew (Put - Call): -0.7%
```

## Helper Functions

The `utils/polygon_helpers.py` module provides reusable functions:

- `list_contracts()`: List all option contracts for a given underlying and expiration
- `fetch_iv_snapshot()`: Get IV snapshot for a specific contract
- `get_stock_price()`: Get historical stock price
- `find_atm_contracts()`: Find ATM call and put contracts

## License

MIT
