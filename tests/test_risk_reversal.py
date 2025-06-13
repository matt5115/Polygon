"""Tests for the RiskReversal strategy."""
import unittest
from datetime import date, timedelta
import numpy as np
import pandas as pd
from backtests.run_mstr_rr405 import RiskReversal

class TestRiskReversal(unittest.TestCase):
    """Test cases for the RiskReversal strategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.strategy = RiskReversal(
            long_call_strike=420,
            short_put_strike=380,
            qty_init=5,
            qty_step=5,
            add_trigger=15,
            take_profit_pct=1.5,
            stop_lvl=385,
            iv_stop=0.10,
            max_qty=25,
            expiry="2025-06-13"
        )
    
    def test_initial_entry(self):
        """Test initial entry conditions."""
        # Should enter when price is above short put strike
        should_enter, reason = self.strategy.should_enter(390, date(2025, 5, 1))
        self.assertTrue(should_enter)
        self.assertIn("Initial entry", reason)
        
        # Should not enter if price is below short put strike
        should_enter, _ = self.strategy.should_enter(370, date(2025, 5, 1))
        self.assertFalse(should_enter)
    
    def test_adding_positions(self):
        """Test adding to positions."""
        # Initial entry
        self.strategy.add_position(390, date(2025, 5, 1), "Initial entry")
        
        # Should not add if price hasn't moved enough
        should_add, _ = self.strategy.should_add(400, date(2025, 5, 2))
        self.assertFalse(should_add)
        
        # Should add if price moved up by add_trigger
        should_add, reason = self.strategy.should_add(405, date(2025, 5, 3))
        self.assertTrue(should_add)
        self.assertIn("+15", reason)
        
        # After adding, update last_add_price
        self.strategy.add_position(405, date(2025, 5, 3), reason)
        
        # Next add should require price to reach 405 + 15 = 420
        should_add, _ = self.strategy.should_add(415, date(2025, 5, 4))
        self.assertFalse(should_add)
        
        should_add, _ = self.strategy.should_add(425, date(2025, 5, 5))
        self.assertTrue(should_add)
    
    def test_exit_conditions(self):
        """Test exit conditions."""
        # Initial entry
        entry_price = 390
        self.strategy.add_position(entry_price, date(2025, 5, 1), "Initial entry")
        
        # Test stop loss
        should_exit, reason = self.strategy.should_exit(
            380,  # Below stop level
            date(2025, 5, 2),
            iv=0.09  # Below IV threshold
        )
        self.assertTrue(should_exit)
        self.assertIn("Stop loss", reason)
        
        # Test take profit
        should_exit, reason = self.strategy.should_exit(
            entry_price * 1.6,  # 60% gain > 50% target
            date(2025, 5, 2),
            current_pnl=1.6  # 60% gain
        )
        self.assertTrue(should_exit)
        self.assertIn("Take profit", reason)
        
        # Test time exit
        expiry = date(2025, 6, 13)
        five_days_before = expiry - timedelta(days=5)
        should_exit, reason = self.strategy.should_exit(
            400,
            five_days_before
        )
        self.assertTrue(should_exit)
        self.assertIn("Approaching expiry", reason)
    
    def test_position_sizing(self):
        """Test position sizing logic."""
        # Initial entry
        self.strategy.add_position(390, date(2025, 5, 1), "Initial entry")
        
        # Add positions until max_qty is reached
        current_price = 390
        expected_positions = 1
        expected_qty = 5  # Initial qty
        
        # We should be able to add 4 more times (5 contracts each)
        # to reach max_qty of 25 (5 initial + 4*5 = 25)
        for i in range(4):
            current_price += 15  # Trigger add
            should_add, reason = self.strategy.should_add(current_price, date(2025, 5, 2 + i))
            self.assertTrue(should_add)
            self.strategy.add_position(current_price, date(2025, 5, 2 + i), reason)
            expected_positions += 1
            expected_qty += 5
        
        # Should have 5 positions (initial + 4 adds)
        self.assertEqual(len(self.strategy.positions), expected_positions)
        
        # Total contracts should be 25 (5 initial + 4*5 adds)
        total_qty = sum(qty for _, qty, _ in self.strategy.positions)
        self.assertEqual(total_qty, expected_qty)
        self.assertEqual(total_qty, self.strategy.max_qty)
        
        # Next add should be rejected (max_qty = 25 reached)
        current_price += 15
        should_add, reason = self.strategy.should_add(current_price, date(2025, 5, 10))
        self.assertFalse(should_add)
        self.assertEqual(reason, "Max position size reached")


if __name__ == "__main__":
    unittest.main()
