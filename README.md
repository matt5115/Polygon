# MSTR Options Trading System

A comprehensive algorithmic trading system for MSTR options, featuring backtesting, live trading, and risk management capabilities.

## Features

- **Automated Trading**: Execute options strategies based on predefined rules
- **Backtesting Framework**: Test strategies on historical data with transaction costs and slippage
- **Risk Management**: Built-in position sizing, stop-loss, and drawdown controls
- **Multiple Strategies**: Support for risk reversals, debit spreads, and more
- **Real-time Monitoring**: Track positions, P&L, and risk metrics
- **Walk-Forward Analysis**: Validate strategy robustness over time
- **Cost-Aware**: Models commissions and slippage for realistic performance

## System Architecture

```
├── backtest/           # Backtesting framework
├── config/             # Configuration files
├── data/               # Market data storage
├── docs/               # Documentation
├── live/               # Live trading components
├── pipelines/          # Data processing pipelines
├── scripts/            # Utility scripts
└── strategies/         # Trading strategies
```

## Prerequisites

- Python 3.9+
- pip (Python package manager)
- Polygon.io API key (for market data)
- Brokerage API access (for live trading)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/mstr-options-trading.git
   cd mstr-options-trading
   ```

2. **Set up the environment**
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt

   # Set up environment variables
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

3. **Run backtests**
   ```bash
   # Run risk reversal strategy
   python backtests/run_mstr_rr405_v3.py
   
   # Run spread matrix
   python backtests/run_spread_matrix.py
   
   # Compare strategies
   python backtests/compare_strategies.py
   ```

4. **Live Trading**
   ```bash
   # Configure live trading
   cp config/live_strategy.yaml.template config/live_strategy.yaml
   # Edit live_strategy.yaml with your parameters
   
   # Start the trading daemon
   python live/trade_daemon.py
   
   # In a separate terminal, start the monitor
   python live/monitor.py
   ```

## Key Components

### Backtesting

- `backtest/backtester.py`: Core backtesting engine
- `backtest/walk_forward.py`: Walk-forward analysis
- `strategies/`: Strategy implementations

### Live Trading

- `live/trade_daemon.py`: Main trading process
- `live/monitor.py`: Position and risk monitoring
- `pipelines/update_mstr_chain.py`: Option chain data updates

### Analysis

- `scripts/select_winner.py`: Strategy selection based on backtest results
- `notebooks/`: Jupyter notebooks for analysis

## Configuration

- `config/selection_criteria.yaml`: Strategy selection criteria
- `config/live_strategy.yaml`: Live trading parameters
- `.env`: Environment variables and API keys

## Documentation

For detailed documentation, see the [docs](docs/) directory, including:

- [Live Trading Runbook](docs/LIVE_TRADING_RUNBOOK.md)
- [Strategy Development Guide](docs/STRATEGY_DEVELOPMENT.md)
- [API Reference](docs/API_REFERENCE.md)

## Testing

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=backtest --cov=strategies tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue or contact the maintainers.

---

**Note**: This is a sophisticated trading system. Always test thoroughly in simulation before trading with real money.

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
