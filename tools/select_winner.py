#!/usr/bin/env python3
"""
Selects the best strategy based on backtest results.

Reads a markdown comparison report, applies selection criteria,
and outputs the winning strategy slug to build/winner.txt.
"""

import argparse
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def load_yaml(path: str) -> Dict:
    """Load and parse YAML configuration."""
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading YAML from {path}: {e}", file=sys.stderr)
        sys.exit(3)


def parse_md_table(path: str) -> List[Dict]:
    """Parse the markdown table into a list of dictionaries."""
    try:
        with open(path) as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {path}: {e}", file=sys.stderr)
        sys.exit(2)

    # Find all table rows (lines starting and ending with |)
    lines = [line.strip() for line in content.split('\n') 
             if line.strip().startswith('|') and line.strip().endswith('|')]
    
    if len(lines) < 2:  # Need at least header and separator
        print(f"No valid markdown table found in {path}", file=sys.stderr)
        sys.exit(2)

    # Skip the separator line (the one with ---)
    header_line = lines[0]
    data_lines = [line for line in lines[1:] if '---' not in line]
    
    # Extract headers (remove leading/trailing | and split)
    headers = [h.strip() for h in header_line.strip('|').split('|')]
    
    rows = []
    for line in data_lines:
        # Split the line into columns
        cols = [c.strip() for c in line.strip('|').split('|')]
        if len(cols) != len(headers):
            continue  # Skip malformed rows
            
        # Extract slug from strategy name (first word before space, lowercase)
        slug = cols[0].split()[0].lower()
        
        # Parse metrics, handling percentages and converting to Decimal
        try:
            row_data = {
                'slug': slug,
                'total_return': Decimal(cols[1].strip('%')) / 100,  # Convert % to decimal
                'win_rate': Decimal(cols[2].strip('%')) / 100,
                'trades': int(cols[3]),
                'avg_win': Decimal(cols[4].strip('%')) / 100,
                'avg_loss': Decimal(cols[5].strip('%').replace('−', '-')) / 100,  # Handle minus sign
                'max_drawdown': Decimal(cols[6].strip('%').replace('−', '-')) / 100,  # Handle minus sign
            }
            rows.append(row_data)
        except (IndexError, ValueError) as e:
            print(f"Error parsing row data: {e} in line: {line}", file=sys.stderr)
            continue
    
    return rows


def apply_filters(rows: List[Dict], criteria: Dict) -> List[Dict]:
    """Apply selection criteria to filter strategies.
    
    Args:
        rows: List of strategy dictionaries with metrics
        criteria: Dictionary of selection criteria
        
    Returns:
        Filtered list of strategies that meet all criteria
    """
    if not rows or not criteria:
        return []
    
    # Convert criteria values to appropriate types
    # Note: min_net_roi is expected in percentage (e.g., 1.0 for 1%)
    min_net_roi = Decimal(str(criteria.get('min_net_roi', 0))) / 100  # Convert % to decimal
    # max_drawdown is expected as a positive number in percentage (e.g., 5.0 for 5%)
    max_drawdown = Decimal(str(criteria.get('max_drawdown', 100))) / 100  # Convert % to decimal
    min_sharpe = Decimal(str(criteria.get('min_sharpe', 0)))
    min_trades = int(criteria.get('min_trades', 0))
    min_win_rate = Decimal(str(criteria.get('min_win_rate', 0))) / 100  # Convert % to decimal
    
    filtered = []
    for row in rows:
        try:
            # Print debug info for the row being processed
            print(f"\nProcessing {row['slug']}:")
            print(f"  total_return={row['total_return']} (min_net_roi={min_net_roi})")
            print(f"  win_rate={row['win_rate']} (min_win_rate={min_win_rate})")
            print(f"  trades={row['trades']} (min_trades={min_trades})")
            print(f"  avg_win={row['avg_win']}, avg_loss={row['avg_loss']}")
            print(f"  max_drawdown={row['max_drawdown']} (max_allowed={max_drawdown})")
            
            # Calculate Sharpe ratio (simplified as win_rate * avg_win + (1-win_rate) * avg_loss) / abs(avg_loss)
            if row['avg_loss'] == 0:  # Avoid division by zero
                sharpe_ratio = Decimal('0')
            else:
                sharpe_ratio = (row['win_rate'] * row['avg_win'] + 
                              (1 - row['win_rate']) * row['avg_loss']) / abs(row['avg_loss'])
            
            # Add sharpe_ratio to the row for later use
            row['sharpe_ratio'] = sharpe_ratio
            print(f"  sharpe_ratio={sharpe_ratio} (min_sharpe={min_sharpe})")
            
            # Apply filters - all conditions must be True
            if not (row['total_return'] >= min_net_roi):
                print(f"  ❌ Failed: total_return {row['total_return']} < {min_net_roi}")
                continue  # Skip if return is too low
                
            if not (abs(row['max_drawdown']) <= max_drawdown):
                print(f"  ❌ Failed: max_drawdown {abs(row['max_drawdown'])} > {max_drawdown}")
                continue  # Skip if drawdown is too high
                
            if not (sharpe_ratio >= min_sharpe):
                print(f"  ❌ Failed: sharpe_ratio {sharpe_ratio} < {min_sharpe}")
                continue  # Skip if Sharpe ratio is too low
                
            if not (row['trades'] >= min_trades):
                print(f"  ❌ Failed: trades {row['trades']} < {min_trades}")
                continue  # Skip if not enough trades
                
            if not (row['win_rate'] >= min_win_rate):
                print(f"  ❌ Failed: win_rate {row['win_rate']} < {min_win_rate}")
                continue  # Skip if win rate is too low
            
            # If we get here, all conditions passed
            print("  ✅ Passed all filters")
            filtered.append(row)
                
        except (KeyError, ValueError) as e:
            print(f"Warning: Error processing row {row.get('slug', 'unknown')}: {e}", file=sys.stderr)
            continue
    
    print(f"\nTotal strategies after filtering: {len(filtered)}")
    return filtered


def choose_best(rows: List[Dict]) -> Optional[str]:
    """Select the best strategy based on Sharpe ratio and drawdown."""
    if not rows:
        return None
        
    # Sort by Sharpe ratio (descending), then by drawdown (ascending)
    sorted_rows = sorted(
        rows, 
        key=lambda x: (-x['sharpe_ratio'], x['max_drawdown'])
    )
    
    return sorted_rows[0]['slug']


def main():
    parser = argparse.ArgumentParser(description='Select the best strategy based on backtest results.')
    parser.add_argument('--source', 
                        default='backtests/comparison/strategy_comparison.md',
                        help='Path to strategy comparison markdown file')
    parser.add_argument('--config',
                        default='config/selection_criteria.yaml',
                        help='Path to selection criteria YAML file')
    args = parser.parse_args()
    
    # Load criteria and parse markdown
    criteria = load_yaml(args.config)
    rows = parse_md_table(args.source)
    
    if not rows:
        print("No valid strategy data found in the comparison report.", file=sys.stderr)
        sys.exit(1)
    
    # Apply filters and select best
    filtered = apply_filters(rows, criteria)
    winner = choose_best(filtered)
    
    if not winner:
        print("No strategy meets the selection criteria.", file=sys.stderr)
        sys.exit(1)
    
    # Ensure build directory exists
    Path("build").mkdir(exist_ok=True)
    
    # Write winner to file
    try:
        with open("build/winner.txt", "w") as f:
            f.write(f"{winner}\n")
        print(f"Selected strategy: {winner}")
    except IOError as e:
        print(f"Error writing to build/winner.txt: {e}", file=sys.stderr)
        sys.exit(2)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
