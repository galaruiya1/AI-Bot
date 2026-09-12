"""Sanity-check HFT YAML without importing Hummingbot."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STRAT = ROOT / "strategies" / "pmm_mister_hft"

ACCOUNT_QUOTE = 365.81
LEVERAGE = 20
CLIP = 800
TAKE_PROFIT = 0.00015
STOP_LOSS = 0.0005


def load(name: str) -> dict:
    return yaml.safe_load((STRAT / name).read_text())


def test_live_and_paper_share_perp_clip_shape():
    live = load("conf_pmm_mister_hft_btc.yml")
    paper = load("conf_pmm_mister_hft_btc_paper.yml")

    assert live["controller_name"] == paper["controller_name"] == "pmm_mister_hft"
    assert live["trading_pair"] == paper["trading_pair"] == "BTC-USDT"
    assert live["connector_name"] == "binance_perpetual"
    assert paper["connector_name"] == "binance_perpetual_testnet"

    margin_per_clip = CLIP / LEVERAGE
    assert margin_per_clip == 40
    assert 2 * margin_per_clip < ACCOUNT_QUOTE

    for cfg in (live, paper):
        assert cfg["tick_mode"] is True
        assert cfg["price_source"] == "best_bid_ask"
        assert cfg["join_touch"] is True
        assert cfg["leverage"] == LEVERAGE
        assert cfg["position_mode"] == "HEDGE"
        assert cfg["order_notional_quote"] == CLIP
        assert cfg["take_profit"] == TAKE_PROFIT
        assert abs(cfg["stop_loss"] - STOP_LOSS) < 1e-12
        assert cfg["time_limit"] == 120
        assert cfg["max_active_executors_by_level"] == 1
        assert cfg["buy_spreads"] == [1]
        assert cfg["sell_spreads"] == [1]
        assert abs(cfg["take_profit"] * CLIP - 0.12) < 1e-9
        assert abs(cfg["stop_loss"] * CLIP - 0.4) < 1e-9
        assert cfg["order_notional_quote"] / cfg["total_amount_quote"] == 0.5


def test_controller_wires_stop_loss_and_clip_size():
    text = (STRAT / "pmm_mister_hft.py").read_text()
    assert "class PMMisterHFTConfig" in text
    assert "class PMMisterHFT" in text
    assert "stop_loss=self.stop_loss" in text
    assert "order_notional_quote" in text
    assert 'default="binance_perpetual"' in text
