#!/usr/bin/env python3
"""Tests for select_winner.py"""

import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, mock_open

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from tools.select_winner import (
    load_yaml, 
    parse_md_table, 
    apply_filters, 
    choose_best
)


class TestSelectWinner(unittest.TestCase):
    """Test cases for select_winner.py"""
    
    def setUp(self):
        """Set up test data."""
        self.test_yaml = """
        min_net_roi: 1.0
        max_drawdown: -5.0
        min_sharpe: 0.5
        min_trades: 3
        min_win_rate: 40.0
        max_cost_ratio: 0.25
        """
        
        self.test_md = """
# MSTR Options Strategies Comparison

*Generated on 2025-06-11 16:50:01*

## Performance Summary

| Strategy | Total Return | Win Rate | Trades | Avg Win % | Avg Loss % | Max Drawdown |
|----------|-------------:|---------:|-------:|----------:|-----------:|-------------:|
| StratA | 5.0% | 60% | 10 | 2.0% | -1.0% | -4.0% |
| StratB | 3.0% | 50% | 8 | 1.5% | -1.5% | -6.0% |
| StratC | 4.0% | 55% | 12 | 3.0% | -2.0% | -3.5% |
"""

    def test_load_yaml(self):
        """Test YAML loading."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(self.test_yaml)
            yaml_path = f.name
        
        try:
            result = load_yaml(yaml_path)
            self.assertEqual(result['min_net_roi'], 1.0)
            self.assertEqual(result['max_drawdown'], -5.0)
            self.assertEqual(result['min_sharpe'], 0.5)
        finally:
            os.unlink(yaml_path)
    
    def test_parse_md_table(self):
        """Test markdown table parsing."""
        # Create a simple markdown table for testing
        test_md = """# Test Table

| Strategy     | Total Return | Win Rate | Trades | Avg Win % | Avg Loss % | Max Drawdown |
|-------------|-------------:|---------:|-------:|----------:|-----------:|-------------:|
| TestStrat   | 5.0%        | 60%      | 10     | 2.0%      | -1.0%      | -4.0%        |
| AnotherStrat| 3.0%        | 55%      | 8      | 1.5%      | -1.5%      | -3.0%        |
"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(test_md)
            md_path = f.name
        
        try:
            # Test with the test file
            rows = parse_md_table(md_path)
            self.assertEqual(len(rows), 2)  # Should have 2 rows of data
            
            # Test first row
            self.assertEqual(rows[0]['slug'], 'teststrat')
            self.assertEqual(float(rows[0]['total_return']), 0.05)
            self.assertEqual(float(rows[0]['win_rate']), 0.6)
            self.assertEqual(rows[0]['trades'], 10)
            self.assertEqual(float(rows[0]['avg_win']), 0.02)
            self.assertEqual(float(rows[0]['avg_loss']), -0.01)
            self.assertEqual(float(rows[0]['max_drawdown']), -0.04)
            
            # Test second row
            self.assertEqual(rows[1]['slug'], 'anotherstrat')
            self.assertEqual(float(rows[1]['total_return']), 0.03)
            
            # Test with a non-existent file (should exit with code 2)
            with self.assertRaises(SystemExit) as cm:
                parse_md_table("nonexistent_file.md")
            self.assertEqual(cm.exception.code, 2)
            
        finally:
            os.unlink(md_path)
    
    def test_apply_filters(self):
        """Test strategy filtering."""
        # Define test criteria - note: values are in percentages as they would be in the YAML
        criteria = {
            'min_net_roi': 1.0,      # 1% minimum return (converted to 0.01 in apply_filters)
            'max_drawdown': 5.0,     # 5% max drawdown (converted to 0.05 in apply_filters)
            'min_sharpe': 0.5,       # Minimum Sharpe ratio (not a percentage)
            'min_trades': 5,          # Minimum number of trades
            'min_win_rate': 40.0      # 40% minimum win rate (converted to 0.4 in apply_filters)
        }
    
        # Test data - only the first row should pass all filters
        # Note: Values are already in decimal form (e.g., 0.05 for 5%)
        rows = [
            # This one should pass all filters
            {'slug': 'goodstrat', 
             'total_return': Decimal('0.05'),  # 5% return > 1% min
             'win_rate': Decimal('0.6'),       # 60% win rate > 40% min
             'trades': 10,                     # 10 trades > 5 min
             'avg_win': Decimal('0.04'),       # 4% average win
             'avg_loss': Decimal('-0.02'),     # -2% average loss
             'max_drawdown': Decimal('-0.04')  # -4% drawdown < 5% max (absolute value comparison)
            },
            # Fails max_drawdown (too large)
            {'slug': 'risky', 
             'total_return': Decimal('0.10'),
             'win_rate': Decimal('0.7'),
             'trades': 8,
             'avg_win': Decimal('0.05'),
             'avg_loss': Decimal('-0.025'),
             'max_drawdown': Decimal('-0.15')  # -15% > 5% max (absolute value comparison)
            },
            # Fails min_win_rate (too low)
            {'slug': 'unlucky', 
             'total_return': Decimal('0.02'),
             'win_rate': Decimal('0.35'),      # 35% < 40% min
             'trades': 12,
             'avg_win': Decimal('0.03'),
             'avg_loss': Decimal('-0.02'),
             'max_drawdown': Decimal('-0.03')
            },
            # Fails min_trades (too few)
            {'slug': 'newstrat', 
             'total_return': Decimal('0.08'),
             'win_rate': Decimal('0.65'),
             'trades': 3,                     # 3 < 5 min
             'avg_win': Decimal('0.04'),
             'avg_loss': Decimal('-0.02'),
             'max_drawdown': Decimal('-0.03')
            }
        ]
    
        # Apply filters
        filtered = apply_filters(rows, criteria)
        
        # Debug: Print filtered results
        print(f"\nFiltered strategies: {[f['slug'] for f in filtered]}")
        
        # Should only have one passing strategy
        self.assertEqual(len(filtered), 1, f"Expected 1 strategy to pass filters, got {len(filtered)}")
        self.assertEqual(filtered[0]['slug'], 'goodstrat')
        
        # Verify Sharpe ratio calculation
        # Expected: (win_rate * avg_win + (1-win_rate) * avg_loss) / abs(avg_loss)
        # (0.6 * 0.04 + 0.4 * -0.02) / 0.02 = (0.024 - 0.008) / 0.02 = 0.8
        expected_sharpe = Decimal('0.8')
        self.assertAlmostEqual(
            float(filtered[0]['sharpe_ratio']), 
            float(expected_sharpe), 
            places=2,
            msg=f"Expected Sharpe ratio ~{expected_sharpe}, got {filtered[0]['sharpe_ratio']}"
        )
    
    def test_choose_best(self):
        """Test strategy selection."""
        rows = [
            {'slug': 'strata', 'sharpe_ratio': Decimal('1.2'), 'max_drawdown': Decimal('-0.04')},
            {'slug': 'strata', 'sharpe_ratio': Decimal('1.5'), 'max_drawdown': Decimal('-0.035')},
            {'slug': 'strata', 'sharpe_ratio': Decimal('1.5'), 'max_drawdown': Decimal('-0.03')},
        ]
        
        best = choose_best(rows)
        self.assertEqual(best, 'strata')  # Should pick the one with max sharpe and min drawdown
    
    @patch('builtins.open', new_callable=mock_open, read_data="""
min_net_roi: 1.0
max_drawdown: 5.0
min_sharpe: 0.5
min_trades: 3
min_win_rate: 40.0
    """.strip())
    @patch('pathlib.Path.mkdir')
    @patch('pathlib.Path.exists', return_value=True)
    def test_main_success(self, mock_exists, mock_mkdir, mock_file):
        """Test main function success case."""
        from tools.select_winner import main
        
        # Create a mock for the file handle
        mock_file_handle = mock_open().return_value
        
        # Create a mock for Path.open that returns our mock file handle
        mock_path = MagicMock()
        mock_path.open.return_value.__enter__.return_value = mock_file_handle
        
        with patch('sys.argv', ['select_winner.py']):
            with patch('tools.select_winner.parse_md_table') as mock_parse:
                with patch('pathlib.Path', return_value=mock_path):
                    # Create a valid row with all required fields
                    test_row = {
                        'slug': 'beststrat',
                        'total_return': Decimal('0.08'),  # 8% > 1% min
                        'win_rate': Decimal('0.65'),       # 65% > 40% min
                        'trades': 12,                      # 12 > 3 min
                        'avg_win': Decimal('0.04'),        # 4% avg win
                        'avg_loss': Decimal('-0.02'),      # -2% avg loss
                        'max_drawdown': Decimal('-0.035')  # -3.5% < 5% max
                    }
        
                    # Add a second row that should be filtered out
                    test_row2 = {
                        'slug': 'badstrat',
                        'total_return': Decimal('0.01'),  # 1% >= 1% min (should pass)
                        'win_rate': Decimal('0.35'),      # 35% < 40% (should fail)
                        'trades': 2,                      # 2 < 3 (should fail)
                        'avg_win': Decimal('0.02'),
                        'avg_loss': Decimal('-0.03'),
                        'max_drawdown': Decimal('-0.10')  # 10% > 5% max (should fail)
                    }
        
                    # Set up the mock to return our test data
                    mock_parse.return_value = [test_row, test_row2]
        
                    # Call the main function and expect it to exit with code 0
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    
                    # Verify the exit code is 0 (success)
                    self.assertEqual(cm.exception.code, 0)
                    
                    # Verify the file was opened in write mode
                    mock_path.open.assert_called_once_with('w')
                    
                    # Verify the winner was written to the file
                    mock_file_handle.write.assert_called_once_with("beststrat\n")


if __name__ == "__main__":
    unittest.main()
