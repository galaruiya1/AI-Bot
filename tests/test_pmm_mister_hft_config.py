"""Sanity-check HFT YAML without importing Hummingbot."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STRAT = ROOT / "strategies" / "pmm_mister_hft"


def load(name: str) -> dict:
    return yaml.safe_load((STRAT / name).read_text())


def test_live_and_paper_share_hft_shape():
    live = load("conf_pmm_mister_hft_btc.yml")
    paper = load("conf_pmm_mister_hft_btc_paper.yml")

    assert live["controller_name"] == paper["controller_name"] == "pmm_mister_hft"
    assert live["trading_pair"] == paper["trading_pair"] == "BTC-USDT"
    assert live["connector_name"] == "binance"
    assert paper["connector_name"] == "binance_paper_trade"

    for cfg in (live, paper):
        assert cfg["tick_mode"] is True
        assert cfg["price_source"] == "best_bid_ask"
        assert cfg["join_touch"] is True
        assert cfg["executor_refresh_time"] == 3
        assert cfg["buy_cooldown_time"] == 4
        assert cfg["max_active_executors_by_level"] == 1
        assert cfg["buy_spreads"] == [1, 3, 8]
        assert cfg["sell_spreads"] == [1, 3, 8]
        assert cfg["take_profit"] >= 0.0004
        assert cfg["min_skew"] < 1
        assert cfg["leverage"] == 1
        tightest = 5 / 20 * cfg["total_amount_quote"] * cfg["portfolio_allocation"]
        assert tightest >= 5


def test_controller_file_present():
    text = (STRAT / "pmm_mister_hft.py").read_text()
    assert "class PMMisterHFTConfig" in text
    assert "class PMMisterHFT" in text
    assert "best_bid_ask" in text
