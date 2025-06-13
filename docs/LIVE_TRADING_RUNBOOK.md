# Live Trading Runbook

This document provides operational guidelines for the MSTR Options Trading System in production.

## System Overview

The trading system consists of the following components:

1. **Trade Daemon** (`live/trade_daemon.py`): Main process that executes trades based on strategy signals
2. **Monitor** (`live/monitor.py`): Monitors positions and enforces risk limits
3. **Option Chain Updater** (`pipelines/update_mstr_chain.py`): Updates option chain data
4. **Strategy Selector** (`scripts/select_winner.py`): Selects the best strategy based on backtest results

## Deployment Flow

### Prerequisites

- Python 3.9+
- Required packages (see `requirements.txt`)
- Configuration files:
  - `config/live_strategy.yaml` (copy from template)
  - `.env` with API keys and secrets

### Initial Setup

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/mstr-options-trading.git
   cd mstr-options-trading
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   cp config/live_strategy.yaml.template config/live_strategy.yaml
   # Edit live_strategy.yaml with your parameters
   ```

### Deployment Steps

1. **Update option chain data** (run before market open)
   ```bash
   python pipelines/update_mstr_chain.py
   ```

2. **Run backtests** (weekly or when strategy changes)
   ```bash
   python backtests/run_mstr_rr405_v3.py
   python backtests/run_spread_matrix.py
   python backtests/compare_strategies.py
   ```

3. **Select best strategy**
   ```bash
   python scripts/select_winner.py
   ```

4. **Update live config** with selected strategy
   ```yaml
   # In config/live_strategy.yaml
   strategy: risk_reversal_405_445  # or winning strategy
   ```

5. **Start the trading daemon**
   ```bash
   nohup python live/trade_daemon.py > trade_daemon.log 2>&1 &
   ```

6. **Start the monitor** (in a separate terminal)
   ```bash
   nohup python live/monitor.py > monitor.log 2>&1 &
   ```

## Monitoring and Maintenance

### Log Files

- `trade_daemon.log`: Trade execution logs
- `monitor.log`: Position monitoring and risk alerts
- `update_chain.log`: Option chain update logs

### Alerting

Set up alerts for:
- Trade executions
- Risk limit breaches
- System errors
- Position size warnings

### Daily Tasks

1. **Pre-Market (8:00 AM ET)**
   - Check for system updates
   - Verify option chain data is up to date
   - Review overnight positions and news

2. **Market Hours (9:30 AM - 4:00 PM ET)**
   - Monitor trade execution
   - Watch for risk alerts
   - Be prepared to intervene if needed

3. **Post-Market (After 4:00 PM ET)**
   - Review daily performance
   - Check for any failed trades
   - Update logs and records

## Emergency Procedures

### Pausing the System

To temporarily pause trading:

1. Stop the trade daemon:
   ```bash
   pkill -f "python live/trade_daemon.py"
   ```

2. Monitor will continue to run and alert on positions

### Shutting Down

To safely shut down the system:

1. Close all positions (manually or via script)
2. Stop the trade daemon and monitor:
   ```bash
   pkill -f "python live/trade_daemon.py"
   pkill -f "python live/monitor.py"
   ```

### Rollback Procedure

If a bad deployment occurs:

1. Stop the trade daemon
2. Revert to previous working version:
   ```bash
   git checkout <previous-commit-hash>
   ```
3. Restart the system

## Risk Management

### Position Limits

- Max position size: 25 contracts
- Max loss per trade: 5% of account
- Max drawdown: 10% of account

### Circuit Breakers

The system will automatically:
- Stop trading if max loss is exceeded
- Close positions if IV drops below 8%
- Halt trading if connectivity is lost

## Support and Contacts

### On-Call Rotation

- **Primary**: [Name] - [Phone] - [Email]
- **Secondary**: [Name] - [Phone] - [Email]
- **DevOps**: [Name] - [Phone] - [Email]

### Escalation Path

1. First responder tries to resolve the issue
2. Escalate to senior trader if unresolved after 15 minutes
3. Escalate to engineering team if technical issue persists

## Appendix

### Common Issues

#### Trade Execution Failures

**Symptom**: Trades not executing
**Solution**:
1. Check API connectivity
2. Verify available margin
3. Check for exchange restrictions

#### Data Feed Issues

**Symptom**: Stale or missing market data
**Solution**:
1. Restart data feed
2. Verify API key limits
3. Check for exchange maintenance

### Recovery Procedures

#### After a Crash

1. Check logs for crash reason
2. Verify position reconciliation
3. Resume trading if conditions are met

#### After a Network Outage

1. Verify connection to exchange
2. Reconcile positions
3. Resume normal operation

### Maintenance Schedule

- **Daily**: Check system status
- **Weekly**: Update option chain data
- **Monthly**: Review and update strategy parameters
- **Quarterly**: Full system audit
