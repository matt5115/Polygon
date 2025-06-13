#!/usr/bin/env python3
"""
Walk-Forward Analysis for Options Trading Strategies

This script performs walk-forward analysis on a trading strategy by:
1. Splitting the historical data into multiple in-sample and out-of-sample periods
2. Optimizing strategy parameters on the in-sample data
3. Testing the optimized parameters on out-of-sample data
4. Compiling performance metrics across all periods
"""
import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('walk_forward.log')
    ]
)
logger = logging.getLogger(__name__)

class WalkForwardAnalyzer:
    """Perform walk-forward analysis on a trading strategy."""
    
    def __init__(self, strategy_class, initial_capital: float = 100000.0):
        """
        Initialize the walk-forward analyzer.
        
        Args:
            strategy_class: The strategy class to test (not an instance)
            initial_capital: Starting capital for backtests
        """
        self.strategy_class = strategy_class
        self.initial_capital = initial_capital
        self.results = []
    
    def run_analysis(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        initial_train_size: int = 180,  # days
        test_size: int = 30,  # days
        step: int = 30,  # days to move forward each iteration
        min_train_size: int = 90  # minimum days for training
    ) -> pd.DataFrame:
        """
        Run walk-forward analysis.
        
        Args:
            data: DataFrame with price data (must have datetime index)
            param_grid: Dictionary of parameters to optimize
            initial_train_size: Initial training period in days
            test_size: Test period in days
            step: Days to move forward each iteration
            min_train_size: Minimum training period in days
            
        Returns:
            DataFrame with walk-forward results
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have a DatetimeIndex")
        
        # Sort data by date
        data = data.sort_index()
        
        # Initialize variables
        start_idx = 0
        end_train_idx = start_idx + initial_train_size
        
        while end_train_idx + test_size <= len(data):
            # Get train and test data
            train_data = data.iloc[start_idx:end_train_idx]
            test_data = data.iloc[end_train_idx:end_train_idx + test_size]
            
            # Skip if not enough data
            if len(train_data) < min_train_size or len(test_data) < test_size // 2:
                logger.info(f"Skipping period: insufficient data")
                start_idx += step
                end_train_idx = start_idx + initial_train_size
                continue
            
            # Get date ranges
            train_start = train_data.index[0].strftime('%Y-%m-%d')
            train_end = train_data.index[-1].strftime('%Y-%m-%d')
            test_start = test_data.index[0].strftime('%Y-%m-%d')
            test_end = test_data.index[-1].strftime('%Y-%m-%d')
            
            logger.info(f"\n=== Walk-Forward Period ===")
            logger.info(f"Train: {train_start} to {train_end} ({len(train_data)} days)")
            logger.info(f"Test:  {test_start} to {test_end} ({len(test_data)} days)")
            
            # Optimize parameters on training data
            logger.info("Optimizing parameters...")
            best_params = self.optimize_parameters(train_data, param_grid)
            
            # Test on out-of-sample data
            logger.info("Testing on out-of-sample data...")
            test_result = self.run_backtest(test_data, best_params)
            
            # Save results
            result = {
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'params': best_params,
                **test_result
            }
            self.results.append(result)
            
            # Log results
            logger.info(f"Test Results: {test_result['total_return']:.2f}% return, "
                       f"Sharpe: {test_result['sharpe_ratio']:.2f}, "
                       f"Max DD: {test_result['max_drawdown']:.2f}%")
            
            # Move window forward
            start_idx += step
            end_train_idx = start_idx + initial_train_size
        
        return pd.DataFrame(self.results)
    
    def optimize_parameters(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        """
        Optimize strategy parameters using grid search.
        
        Args:
            data: Training data
            param_grid: Dictionary of parameters to optimize
            
        Returns:
            Dictionary of best parameters
        """
        from itertools import product
        from tqdm import tqdm
        
        # Generate all parameter combinations
        keys = param_grid.keys()
        values = param_grid.values()
        param_combinations = [dict(zip(keys, combo)) for combo in product(*values)]
        
        best_score = -float('inf')
        best_params = None
        
        logger.info(f"Testing {len(param_combinations)} parameter combinations...")
        
        # Test each parameter combination
        for params in tqdm(param_combinations):
            try:
                # Run backtest with current parameters
                result = self.run_backtest(data, params)
                
                # Use Sharpe ratio as the optimization metric
                score = result['sharpe_ratio']
                
                # Update best parameters if current score is better
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    
            except Exception as e:
                logger.warning(f"Error with params {params}: {e}")
                continue
        
        logger.info(f"Best parameters: {best_params} (Sharpe: {best_score:.2f})")
        return best_params
    
    def run_backtest(
        self,
        data: pd.DataFrame,
        params: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Run a backtest with the given parameters.
        
        Args:
            data: Price data for backtesting
            params: Strategy parameters
            
        Returns:
            Dictionary of performance metrics
        """
        # Initialize strategy with given parameters
        strategy = self.strategy_class(**params)
        
        # In a real implementation, this would use your backtester
        # For now, we'll return mock results
        # Replace this with actual backtest code
        
        # Mock implementation
        returns = np.random.normal(0.0005, 0.01, len(data))  # Random returns
        equity = self.initial_capital * (1 + returns).cumprod()
        
        # Calculate metrics
        total_return = (equity.iloc[-1] / self.initial_capital - 1) * 100
        sharpe_ratio = np.sqrt(252) * returns.mean() / (returns.std() + 1e-9)
        
        # Calculate max drawdown
        rolling_max = equity.cummax()
        drawdowns = (equity - rolling_max) / rolling_max
        max_drawdown = drawdowns.min() * 100
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'num_trades': len(returns) // 10,  # Mock
            'win_rate': 0.6,  # Mock
            'profit_factor': 1.5  # Mock
        }
    
    def plot_results(self, results: pd.DataFrame, output_file: Optional[str] = None):
        """
        Plot walk-forward analysis results.
        
        Args:
            results: DataFrame from run_analysis()
            output_file: Optional path to save the plot
        """
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        sns.set_style("whitegrid")
        
        # Plot cumulative returns
        plt.figure(figsize=(12, 6))
        
        # Plot test period returns
        plt.bar(
            range(len(results)),
            results['total_return'],
            label='Test Period Return (%)',
            alpha=0.7
        )
        
        # Add reference lines and annotations
        plt.axhline(0, color='black', linestyle='--', linewidth=0.7)
        plt.xticks(range(len(results)), results['test_start'], rotation=45, ha='right')
        
        plt.title('Walk-Forward Test Period Returns')
        plt.ylabel('Return (%)')
        plt.xlabel('Test Period')
        plt.legend()
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file)
            logger.info(f"Saved plot to {output_file}")
        else:
            plt.show()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run walk-forward analysis on a trading strategy.')
    parser.add_argument('--strategy', type=str, required=True,
                        help='Name of the strategy class to test')
    parser.add_argument('--data', type=str, required=True,
                        help='Path to price data CSV file')
    parser.add_argument('--output', type=str, default='walk_forward_results.csv',
                        help='Output file for results (CSV)')
    parser.add_argument('--plot', type=str, default=None,
                        help='Output file for plot (optional)')
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # Load data
    try:
        data = pd.read_csv(args.data, parse_dates=['date'], index_col='date')
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        sys.exit(1)
    
    # Import strategy class
    try:
        module_name, class_name = args.strategy.rsplit('.', 1)
        module = __import__(module_name, fromlist=[class_name])
        strategy_class = getattr(module, class_name)
    except Exception as e:
        logger.error(f"Error importing strategy class: {e}")
        sys.exit(1)
    
    # Define parameter grid for optimization
    # This should be customized based on the strategy
    param_grid = {
        'qty_init': [1, 2, 5],
        'stop_loss_pct': [0.90, 0.95, 0.98],
        'take_profit_pct': [1.10, 1.20, 1.30],
        'add_trigger': [0.10, 0.15, 0.20]
    }
    
    # Run walk-forward analysis
    analyzer = WalkForwardAnalyzer(strategy_class)
    results = analyzer.run_analysis(
        data=data,
        param_grid=param_grid,
        initial_train_size=180,  # 6 months
        test_size=30,  # 1 month
        step=30  # Move forward 1 month each time
    )
    
    # Save results
    results.to_csv(args.output, index=False)
    logger.info(f"Saved results to {args.output}")
    
    # Generate plot if requested
    if args.plot:
        analyzer.plot_results(results, output_file=args.plot)

if __name__ == "__main__":
    main()
