# Options Trade Manager

A FastAPI-based application for managing and tracking options trades with Polygon.io integration.

## Features

- Track Cash-Secured Puts (CSP) and Covered Calls (CC)
- Store trade details including strikes, premiums, and greeks
- Simulate trade outcomes
- RESTful API for trade management
- SQLite database with SQLAlchemy ORM
- Pydantic data validation

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- Polygon.io API key

## Setup

1. Clone the repository
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the example environment file and update with your settings:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Polygon.io API key

## Running the Application

1. Initialize the database:
   ```bash
   python -c "from db import init_db; init_db()"
   ```

2. Start the FastAPI development server:
   ```bash
   uvicorn app:app --reload
   ```

3. Access the API documentation at: http://localhost:8000/docs

## API Endpoints

- `GET /health` - Health check
- `POST /trades/` - Create a new trade
- `GET /trades/` - List all trades
- `GET /trades/{trade_id}` - Get a specific trade
- `PATCH /trades/{trade_id}` - Update a trade
- `DELETE /trades/{trade_id}` - Delete a trade

## Database

- The application uses SQLite by default (stored in `trades.db`)
- To use PostgreSQL or MySQL, update the `DATABASE_URL` in `.env`

## Testing

Run the test suite with:

```bash
pytest
```

## License

MIT
