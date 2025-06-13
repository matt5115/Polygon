# MSTR Options Backtesting Framework

A comprehensive, cost-aware backtesting framework for evaluating MSTR options trading strategies with realistic transaction costs and slippage modeling.

## Key Features

- **Cost-Aware Backtesting**: Models commissions, fees, and slippage
- **Multiple Strategy Support**: Risk reversals, debit/credit spreads, and more
- **Walk-Forward Analysis**: Validate strategy robustness over time
- **Performance Metrics**: Comprehensive risk/reward statistics
- **Trade Simulation**: Realistic order execution modeling

## Available Strategies

### 1. Risk Reversal 405/445 (v3)
- **Description**: Long 445 Call / Short 405 Put
- **Key Parameters**:
  - Initial contracts: 5
  - Max position: 25 contracts
  - Scale-in: Add 5 contracts when MSTR closes +$15 above last add-level
  - Stop-loss: Close if MSTR ≤ $389
  - Time exit: 5 days before expiry
- **Cost Model**: $0.65 per contract + $0.01 per contract exchange fee
- **Backtest Script**: `run_mstr_rr405_v3.py`
- **Report**: `mstr_rr405_v3/report.md`

### 2. Debit Spread Matrix
- **Description**: Various call/put debit spreads
- **Available Spreads**:
  - 395/425 Call Debit Spread
  - 400/430 Call Debit Spread
  - 390/420 Put Debit Spread
- **Cost Model**: $0.65 per leg + $0.01 per contract
- **Backtest Script**: `run_spread_matrix.py`
- **Report**: `spread_matrix/comparison.md`

## Getting Started

### Prerequisites

- Python 3.9+
- Polygon.io API key
- Redis (for caching)

### Installation

1. Clone the repository and install dependencies:
   ```bash
   git clone https://github.com/yourusername/mstr-options-trading.git
   cd mstr-options-trading
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Polygon.io API key and settings
   ```

## Running Backtests

### Single Strategy Backtest

```bash
# Run Risk Reversal v3 strategy
python backtests/run_mstr_rr405_v3.py

# Run spread matrix (multiple strategies)
python backtests/run_spread_matrix.py
```

### Compare Multiple Strategies

```bash
# Generate comparison report
python backtests/compare_strategies.py

# View the report
open backtests/comparison/strategy_comparison.md
```

### Walk-Forward Analysis

```bash
# Run walk-forward analysis on a strategy
python backtest/walk_forward.py --strategy strategies.RiskReversalStrategy --data data/mstr_ohlcv.csv
```

## Backtest Reports

Backtest reports include the following metrics:

- **Performance**: Total return, annualized return, Sharpe ratio
- **Risk Metrics**: Max drawdown, volatility, Value at Risk (VaR)
- **Trade Analysis**: Win rate, profit factor, average win/loss
- **Cost Analysis**: Total commissions, slippage, cost/revenue ratio
- **Trade Log**: Detailed log of all trades with entry/exit prices

## Strategy Development

### Creating a New Strategy

1. Create a new strategy class in `backtest/strategies/`:
   ```python
   from backtest.strategies.base import BaseStrategy
   
   class MyStrategy(BaseStrategy):
       def __init__(self, **params):
           super().__init__(**params)
           # Initialize your strategy
   
       def generate_signals(self, data):
           # Implement your signal generation logic
           pass
   ```

2. Create a backtest runner script in `backtests/`:
   ```python
   from backtest.backtester import Backtester
   from backtest.strategies.my_strategy import MyStrategy
   
   def main():
       strategy = MyStrategy(param1=value1, param2=value2)
       backtester = Backtester(strategy)
       results = backtester.run()
       backtester.generate_report()
   
   if __name__ == "__main__":
       main()
   ```

3. Add your strategy to the comparison script if needed.

## Cost Modeling

The backtester models the following costs:

1. **Commissions**: Fixed per-contract fees
2. **Exchange Fees**: Per-contract exchange fees
3. **Slippage**: Based on bid-ask spread and order size
4. **Market Impact**: For larger positions

Adjust cost parameters in the strategy configuration or backtest runner.

## Performance Optimization

For faster backtesting:

1. Enable caching of market data
2. Use vectorized operations where possible
3. Run with `--fast` flag for reduced precision but faster execution
4. Use a smaller date range for initial testing

## Troubleshooting

### Common Issues

1. **Missing Data**:
   - Verify your Polygon.io API key has options data access
   - Check the data directory for missing files

2. **Performance Issues**:
   - Reduce the backtest date range
   - Increase the timeframe (e.g., daily instead of minute data)
   - Disable detailed logging

3. **Infinite Loops**:
   - Check for recursive signal generation
   - Verify exit conditions are properly defined

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Disclaimer

This software is for educational purposes only. Past performance is not indicative of future results. Always test strategies thoroughly before trading with real money.
