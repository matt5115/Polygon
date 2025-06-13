"""
Compare performance of MSTR options strategies with cost awareness.
"""
import os
import glob
import pandas as pd
from datetime import datetime
from pathlib import Path

def read_markdown_report(report_path):
    """Extract key metrics from a markdown report with cost awareness."""
    with open(report_path, 'r') as f:
        lines = f.readlines()
    
    metrics = {}
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        # Track current section
        if line.startswith('## '):
            current_section = line[3:].strip()
            continue
            
        # Extract key-value pairs
        if ':' in line and current_section in ['Performance Summary', 'Cost Summary']:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Clean up values
            if '%' in value:
                value = float(value.replace('%', '').strip())
            elif '$' in value:
                value = float(value.replace('$', '').replace(',', '').strip())
            elif value.replace('.', '').isdigit():
                value = float(value)
                
            metrics[key] = value
    
    # Extract trades
    trades = []
    in_trades = False
    
    for line in lines:
        if '## Trade Log' in line:
            in_trades = True
            continue
        if line.startswith('##') and in_trades:
            in_trades = False
            continue
            
        if in_trades and '|' in line and 'Date' not in line and '--' not in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 7:  # Ensure we have all columns including costs
                try:
                    trade = {
                        'date': parts[0],
                        'action': parts[1],
                        'price': float(parts[2].replace('$', '')),
                        'qty': int(parts[3]),
                        'reason': parts[4],
                        'pnl_pct': float(parts[5].strip('%')),
                        'commission': float(parts[6].replace('$', '')),
                        'slippage': float(parts[7].replace('$', '')) if len(parts) > 7 else 0.0
                    }
                    trades.append(trade)
                except (ValueError, IndexError) as e:
                    print(f"Warning: Could not parse trade line: {line}")
    
    # Calculate trade statistics
    trade_pnls = [t['pnl_pct'] for t in trades if t['action'] == 'SELL']
    total_commissions = sum(t.get('commission', 0) for t in trades)
    total_slippage = sum(t.get('slippage', 0) for t in trades)
    
    return {
        'trades': trades,
        'total_return': metrics.get('Net Return %', 0.0),
        'gross_return': metrics.get('Gross Return %', 0.0),
        'win_rate': metrics.get('Win Rate %', 0.0),
        'max_drawdown': abs(metrics.get('Max Drawdown %', 0.0)),
        'sharpe_ratio': metrics.get('Sharpe Ratio', 0.0),
        'total_commissions': total_commissions,
        'total_slippage': total_slippage,
        'total_costs': total_commissions + total_slippage,
        'trades_count': len([t for t in trades if t['action'] == 'SELL']),
        'avg_win': sum(p for p in trade_pnls if p > 0) / max(1, sum(1 for p in trade_pnls if p > 0)) if trade_pnls else 0,
        'avg_loss': sum(p for p in trade_pnls if p < 0) / max(1, sum(1 for p in trade_pnls if p < 0)) if trade_pnls and any(p < 0 for p in trade_pnls) else 0,
        'profit_factor': abs(sum(p for p in trade_pnls if p > 0) / sum(p for p in trade_pnls if p < 0)) if trade_pnls and any(p < 0 for p in trade_pnls) else float('inf')
    }

def generate_comparison():
    """Generate comparison report for all strategies."""
    # Ensure output directory exists
    os.makedirs("backtests/comparison", exist_ok=True)
    
    # Get all strategy reports
    strategies = [
        {
            'name': 'Risk Reversal 380/420',
            'path': 'backtests/mstr_rr405_v2/report.md',
            'description': 'Long 420C / Short 380P, scale-in at +$15, exit at $389 stop or $440 target',
        },
        {
            'name': 'Call Debit Spread 400/430',
            'path': 'backtests/mstr_debit400_430/report.md',
            'description': 'Long 400C / Short 430C, 10 contracts',
        },
    ]
    
    # Load all strategy data
    for strat in strategies:
        if os.path.exists(strat['path']):
            strat.update(read_markdown_report(strat['path']))
    
    # Generate markdown report
    report = "# MSTR Options Strategies Comparison\n\n"
    report += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
    
    # Summary table
    report += "## Performance Summary\n\n"
    report += "| Strategy | Total Return | Win Rate | Trades | Avg Win % | Avg Loss % | Max Drawdown |\n"
    report += "|----------|-------------:|---------:|-------:|----------:|-----------:|-------------:|\n"
    
    for strat in strategies:
        report += f"| {strat['name']} | "
        report += f"{strat.get('total_return', 0):.1f}% | "
        report += f"{strat.get('win_rate', 0):.1f}% | "
        report += f"{strat.get('num_trades', 0)} | "
        report += f"{strat.get('avg_win', 0):.1f}% | "
        report += f"{strat.get('avg_loss', 0):.1f}% | "
        report += f"{strat.get('max_drawdown', 0):.1f}% |\n"
    
    # Strategy details
    report += "\n## Strategy Details\n\n"
    for strat in strategies:
        report += f"### {strat['name']}\n\n"
        report += f"*{strat['description']}*\n\n"
        
        if 'trades' in strat and strat['trades']:
            report += "#### Trades\n\n"
            report += "| Date | Action | Price | Qty | Reason | PnL % |\n"
            report += "|------|--------|------:|----:|--------|------:|\n"
            
            for trade in strat['trades']:
                report += f"| {trade['date']} | {trade['action']} | ${trade['price']:.2f} | {trade['qty']} | {trade['reason']} | {trade['pnl_pct']:+.1f}% |\n"
            
            report += "\n"
    
    # Save report
    report_path = "backtests/comparison/strategy_comparison.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"Comparison report generated: {report_path}")
    return report_path

if __name__ == "__main__":
    generate_comparison()
