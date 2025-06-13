# Backtest Report: MSTR Risk Reversal

## Strategy Parameters
- **Underlying**: MSTR
- **Start Date**: 2025-05-12
- **End Date**: 2025-06-08
- **Initial Capital**: $1,400,000.00
- **Initial Contracts**: 5
- **Max Contracts**: 25
- **Long Call Strike**: $420
- **Short Put Strike**: $380
- **Add Trigger**: +$15
- **Take Profit**: 1.5x
- **Stop Loss**: $385 (with IV ≤ 10%)

## Performance Summary
- **Total Return**: 0.0%
- **Max Drawdown**: 0.0%
- **Number of Trades**: 3


## Trade Log

| Date | Action | Price | Qty | Reason | PnL % |
|------|--------|-------|-----|--------|-------|
| 2025-05-12 | BUY | $404.90 | 5 | Initial entry |  |
| 2025-05-13 | BUY | $421.61 | 5 | Price moved +15 above last add level |  |
| 2025-05-13 | SELL | $421.61 | 10 | Take profit reached: 4.1x | 2.0% |
| 2025-05-14 | BUY | $416.75 | 5 | Initial entry |  |
| 2025-05-23 | SELL | $369.51 | 5 | Stop loss triggered at 369.51 with IV 0.0% | -11.3% |
| 2025-06-03 | BUY | $387.43 | 5 | Initial entry |  |
| 2025-06-04 | SELL | $378.10 | 5 | Stop loss triggered at 378.1 with IV 0.0% | -2.4% |

