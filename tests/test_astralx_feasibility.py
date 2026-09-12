"""Contract-size mapping for the AstralX/Websea BTC perpetual clip."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "astralx-feasibility.md"
SNIPPET = (
    ROOT
    / "strategies"
    / "pmm_mister_hft"
    / "conf_pmm_mister_hft_btc_astralx.yml.snippet"
)

CONTRACT_SIZE_BTC = 0.001
MIN_CONTRACTS = 1
TICK = 0.1
TARGET_NOTIONAL = 800
LEVERAGE = 20
ACCOUNT_QUOTE = 365.81
TAKE_PROFIT = 0.00015
STOP_LOSS = 0.0005
# Snapshot mid from 2026-09-12 oapi.websea.com book (bid 77323.3 / ask 77323.4).
MID = 77323.35


def nearest_contracts(notional: float, mid: float) -> int:
    raw = notional / (mid * CONTRACT_SIZE_BTC)
    n = max(MIN_CONTRACTS, round(raw))
    return n


def test_ten_contracts_is_closest_to_800_usdt():
    n = nearest_contracts(TARGET_NOTIONAL, MID)
    assert n == 10
    notional = n * CONTRACT_SIZE_BTC * MID
    assert abs(notional - 773.2335) < 1e-6
    assert abs(notional - TARGET_NOTIONAL) < abs(
        11 * CONTRACT_SIZE_BTC * MID - TARGET_NOTIONAL
    )


def test_dual_clip_margin_fits_account():
    notional = 10 * CONTRACT_SIZE_BTC * MID
    margin_both = 2 * notional / LEVERAGE
    assert margin_both < ACCOUNT_QUOTE
    assert margin_both < 80


def test_take_profit_is_far_from_one_tick_spread():
    spread_bps = (TICK / MID) * 10_000
    tp_ticks = (MID * TAKE_PROFIT) / TICK
    sl_ticks = (MID * STOP_LOSS) / TICK
    assert spread_bps < 0.2
    assert 110 < tp_ticks < 120
    assert 380 < sl_ticks < 395


def test_docs_and_snippet_exist():
    text = DOC.read_text(encoding="utf-8")
    snippet = SNIPPET.read_text(encoding="utf-8")
    assert "不能把现有 Hummingbot" in text
    assert "qty_contracts: 10" in snippet
    assert "LIMIT_MAKER" in snippet
    assert "binance_perpetual" in snippet
