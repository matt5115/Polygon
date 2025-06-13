from live.futures_adapter import round_to_tick, dollar_risk, TICK_VALUE


def test_round_to_tick():
    assert round_to_tick(110027) == 110025
    assert round_to_tick(110028) == 110030


def test_dollar_risk():
    stop_ticks = 45  # 45 × $0.50
    assert dollar_risk(stop_ticks, qty=1) == 22.5
    assert dollar_risk(stop_ticks, qty=4) == 90.0
