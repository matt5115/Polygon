# Strategy Development Guide

This guide explains how to develop, test, and deploy custom trading strategies in the MSTR Options Trading System.

## Table of Contents

1. [Strategy Architecture](#strategy-architecture)
2. [Creating a New Strategy](#creating-a-new-strategy)
3. [Backtesting Your Strategy](#backtesting-your-strategy)
4. [Walk-Forward Validation](#walk-forward-validation)
5. [Live Deployment](#live-deployment)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Strategy Architecture

### Core Components

1. **BaseStrategy**: Abstract base class that all strategies must implement
2. **Backtester**: Handles the backtesting logic and performance metrics
3. **DataHandler**: Manages market data loading and preprocessing
4. **ExecutionHandler**: Simulates order execution with slippage and commissions
5. **Portfolio**: Trades and tracks positions and P&L

### Data Flow

1. Market data is loaded and preprocessed
2. The strategy generates signals based on the data
3. Signals are converted into orders
4. The execution handler fills orders with realistic costs
5. The portfolio updates positions and calculates P&L
6. Performance metrics are calculated and reported

## Creating a New Strategy

### Step 1: Create a Strategy Class

Create a new Python file in `backtest/strategies/`:

```python
from backtest.strategies.base import BaseStrategy
import pandas as pd

class MyStrategy(BaseStrategy):
    """
    My custom options trading strategy.
    
    Parameters:
    -----------
    param1 : type
        Description of param1
    param2 : type, default=value
        Description of param2
    """
    
    def __init__(self, param1: float, param2: int = 10, **kwargs):
        super().__init__(**kwargs)
        self.param1 = param1
        self.param2 = param2
        
    def calculate_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate any indicators or features needed for signal generation."""
        # Example: Calculate 20-day moving average
        data['sma_20'] = data['close'].rolling(window=20).mean()
        return data
        
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals based on the strategy logic."""
        signals = pd.Series(0, index=data.index)
        
        # Example: Long when price is above SMA
        signals[data['close'] > data['sma_20']] = 1  # Long signal
        signals[data['close'] <= data['sma_20']] = -1  # Exit/Short signal
        
        return signals
        
    def generate_orders(self, signals: pd.Series, data: pd.DataFrame) -> list:
        """Convert signals into orders with position sizing and risk management."""
        orders = []
        position = 0
        
        for i in range(1, len(signals)):
            if signals.iloc[i] != signals.iloc[i-1]:  # Signal changed
                if signals.iloc[i] == 1:  # Enter long
                    orders.append({
                        'timestamp': data.index[i],
                        'symbol': data['symbol'].iloc[i],
                        'action': 'BUY',
                        'quantity': self.position_size,
                        'price': data['close'].iloc[i]
                    })
                    position = 1
                elif signals.iloc[i] == -1:  # Exit position
                    orders.append({
                        'timestamp': data.index[i],
                        'symbol': data['symbol'].iloc[i],
                        'action': 'SELL',
                        'quantity': self.position_size * position,
                        'price': data['close'].iloc[i]
                    })
                    position = 0
        
        return orders
```

### Step 2: Implement Required Methods

Your strategy must implement these methods:

1. `__init__`: Initialize parameters and call `super().__init__()`
2. `calculate_features`: Calculate any indicators or features
3. `generate_signals`: Generate trading signals (-1, 0, 1)
4. `generate_orders`: Convert signals into orders with position sizing

## Backtesting Your Strategy

### Create a Backtest Script

Create a new file in `backtests/`:

```python
#!/usr/bin/env python3
"""
Backtest for MyStrategy.
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from backtest.backtester import Backtester
from backtest.strategies.my_strategy import MyStrategy
from backtest.data.historical import HistoricalDataHandler

def main():
    # Strategy parameters
    params = {
        'param1': 0.5,
        'param2': 20,
        'initial_capital': 100000,
        'position_size': 5,  # Number of contracts
        'commission': 0.65,  # Per contract
        'slippage': 0.01,    # As % of price
    }
    
    # Initialize strategy
    strategy = MyStrategy(**params)
    
    # Load data
    data_handler = HistoricalDataHandler()
    data = data_handler.load_data(
        symbol='MSTR',
        start_date='2023-01-01',
        end_date='2023-12-31',
        timeframe='1d'
    )
    
    # Run backtest
    backtester = Backtester(strategy, data)
    results = backtester.run()
    
    # Generate report
    backtester.generate_report(
        output_dir='backtests/results/my_strategy',
        plot=True
    )

if __name__ == "__main__":
    main()
```

### Run the Backtest

```bash
python backtests/run_my_strategy.py
```

### Analyze Results

Check the generated report in `backtests/results/my_strategy/`:
- `report.md`: Performance metrics and trade log
- `equity_curve.png`: Equity curve over time
- `drawdown.png`: Drawdown chart
- `trades.csv`: Detailed trade log

## Walk-Forward Validation

To validate your strategy's robustness:

```python
from backtest.walk_forward import WalkForwardAnalyzer

# Define parameter grid for optimization
param_grid = {
    'param1': [0.3, 0.5, 0.7],
    'param2': [10, 20, 30],
}

# Initialize analyzer
analyzer = WalkForwardAnalyzer(
    strategy_class=MyStrategy,
    initial_train_size=180,  # days
    test_size=30,            # days
    step=30,                 # days
    param_grid=param_grid
)

# Run walk-forward analysis
results = analyzer.run(data)
analyzer.plot_results()
```

## Live Deployment

### 1. Update Live Configuration

Edit `config/live_strategy.yaml`:

```yaml
strategy: my_strategy
params:
  param1: 0.5
  param2: 20
  position_size: 5
  max_position: 25
  stop_loss: 0.95  # 5% stop loss

trading:
  enabled: true
  max_trades_per_day: 5
  max_risk_per_trade: 0.02  # 2% of capital
  
notifications:
  email: your.email@example.com
  slack_webhook: https://hooks.slack.com/...
```

### 2. Deploy the Strategy

```bash
# Start trade daemon
nohup python live/trade_daemon.py > logs/trade_daemon.log 2>&1 &


# Start monitor
nohup python live/monitor.py > logs/monitor.log 2>&1 &
```

## Best Practices

### Strategy Development

1. **Start Simple**: Begin with a simple strategy and add complexity gradually
2. **Use Walk-Forward**: Always validate with walk-forward analysis
3. **Consider Costs**: Account for commissions, slippage, and market impact
4. **Risk Management**: Implement proper position sizing and stop-losses
5. **Parameter Sensitivity**: Test how sensitive your strategy is to parameter changes

### Code Quality

1. **Type Hints**: Use Python type hints for better code clarity
2. **Docstrings**: Document all classes and methods
3. **Logging**: Use the built-in logging system
4. **Testing**: Write unit tests for your strategy logic
5. **Version Control**: Use Git for version control

## Troubleshooting

### Common Issues

1. **No Trades Executed**
   - Check if data is loaded correctly
   - Verify signal generation logic
   - Ensure position sizing is not zero

2. **Poor Performance**
   - Check for look-ahead bias
   - Review transaction costs
   - Test different parameter values

3. **Runtime Errors**
   - Check logs for error messages
   - Verify data types and shapes
   - Ensure all required columns are present in the data

### Getting Help

1. Check the [FAQ](#faq)
2. Search the issue tracker
3. Open a new issue with:
   - Strategy code
   - Backtest results
   - Error messages
   - Steps to reproduce

## FAQ

### How do I add a new indicator?

Create a method in your strategy class to calculate the indicator and call it from `calculate_features`.

### How do I implement a trailing stop?

Override the `update_trailing_stop` method in your strategy class.

### How do I access options chain data?

Use the `get_options_chain` method in your strategy:

```python
def generate_signals(self, data):
    # Get options chain for next expiration
    chain = self.get_options_chain(
        symbol='MSTR',
        expiration='2023-12-15',
        option_type='call'
    )
    # Your signal logic here
```

### How do I optimize strategy parameters?

Use the built-in parameter optimization:

```python
from backtest.optimization import GridSearchOptimizer

optimizer = GridSearchOptimizer(
    strategy_class=MyStrategy,
    param_grid={
        'param1': [0.1, 0.3, 0.5],
        'param2': [10, 20, 30]
    },
    metric='sharpe_ratio'  # or 'total_return', 'max_drawdown', etc.
)

best_params, best_score = optimizer.optimize(data)
print(f"Best parameters: {best_params}")
print(f"Best score: {best_score}")
```

## Conclusion

This guide covered the basics of developing, testing, and deploying a trading strategy in the MSTR Options Trading System. For more advanced topics, refer to the API documentation and example strategies in the `examples/` directory.
