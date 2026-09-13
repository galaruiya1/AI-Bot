#!/usr/bin/env python3
"""Inventory and P&L invariants for the two grid state machines."""

from __future__ import annotations

import unittest

try:
    from compare import (
        DEFAULT_P0,
        DEFAULT_QTY,
        DualOpen,
        NeutralMaker,
        RANGE_PATH,
        TREND_PATH,
        run_path,
    )
except ImportError:  # python -m unittest from repo root
    from grid.compare import (
        DEFAULT_P0,
        DEFAULT_QTY,
        DualOpen,
        NeutralMaker,
        RANGE_PATH,
        TREND_PATH,
        run_path,
    )


class NeutralMakerPathTests(unittest.TestCase):
    def test_up_one_grid_opens_only_short(self) -> None:
        e = run_path(NeutralMaker(), [0, 1])
        self.assertEqual(e.long_qty(), 0.0)
        self.assertEqual(e.short_qty(), DEFAULT_QTY)
        self.assertEqual([p.level for p in e.shorts], [1])
        self.assertEqual(len(e.fills), 1)
        self.assertTrue(e.fills[0].maker)

    def test_up_then_back_closes_short_flat(self) -> None:
        e = run_path(NeutralMaker(), [0, 1, 0])
        self.assertEqual(e.long_qty(), 0.0)
        self.assertEqual(e.short_qty(), 0.0)
        gross = DEFAULT_QTY * (e.px(1) - e.px(0))
        self.assertAlmostEqual(e.realized, gross)
        self.assertEqual(len(e.fills), 2)

    def test_down_one_grid_opens_only_long(self) -> None:
        e = run_path(NeutralMaker(), [0, -1])
        self.assertEqual(e.long_qty(), DEFAULT_QTY)
        self.assertEqual(e.short_qty(), 0.0)
        self.assertEqual([p.level for p in e.longs], [-1])

    def test_full_range_two_round_trips(self) -> None:
        e = run_path(NeutralMaker(), RANGE_PATH)
        self.assertEqual(e.long_qty(), 0.0)
        self.assertEqual(e.short_qty(), 0.0)
        grid = DEFAULT_QTY * (e.px(1) - e.px(0))
        self.assertAlmostEqual(e.realized, 2 * grid)
        self.assertEqual(len(e.fills), 4)
        last = e.snapshots[-1]
        self.assertLess(last.equity, last.realized)  # fees reduce equity
        # 4 maker fills at ~2bp each vs 2bp gross per round trip → net negative at 1bp
        self.assertLess(last.equity, 0.0)

    def test_trend_accumulates_shorts_linearly(self) -> None:
        e = run_path(NeutralMaker(), TREND_PATH)
        self.assertEqual(e.long_qty(), 0.0)
        self.assertEqual(e.short_qty(), 4 * DEFAULT_QTY)
        self.assertEqual([p.level for p in e.shorts], [1, 2, 3, 4])
        self.assertEqual(e.realized, 0.0)


class DualOpenPathTests(unittest.TestCase):
    def test_start_locks_both_sides(self) -> None:
        e = run_path(DualOpen(), [0])
        self.assertEqual(e.long_qty(), DEFAULT_QTY)
        self.assertEqual(e.short_qty(), DEFAULT_QTY)
        self.assertEqual(len(e.fills), 2)
        self.assertFalse(any(f.maker for f in e.fills))

    def test_up_closes_prev_long_leaves_net_short(self) -> None:
        e = run_path(DualOpen(), [0, 1])
        self.assertEqual(e.long_qty(), DEFAULT_QTY)
        self.assertEqual(e.short_qty(), 2 * DEFAULT_QTY)
        self.assertEqual([p.level for p in e.longs], [1])
        self.assertEqual([p.level for p in e.shorts], [0, 1])

    def test_up_then_back_matches_user_story(self) -> None:
        e = run_path(DualOpen(), [0, 1, 0])
        # leftover: short@0, long@1, plus a fresh lock at 0
        self.assertEqual([p.level for p in e.longs], [1, 0])
        self.assertEqual([p.level for p in e.shorts], [0, 0])
        self.assertEqual(e.long_qty(), 2 * DEFAULT_QTY)
        self.assertEqual(e.short_qty(), 2 * DEFAULT_QTY)
        grid = DEFAULT_QTY * (e.px(1) - e.px(0))
        self.assertAlmostEqual(e.realized, 2 * grid)
        self.assertAlmostEqual(e.unrealized(0), -grid)

    def test_range_uses_far_more_fills_than_maker_grid(self) -> None:
        maker = run_path(NeutralMaker(), RANGE_PATH)
        dual = run_path(DualOpen(), RANGE_PATH)
        self.assertEqual(len(maker.fills), 4)
        self.assertEqual(len(dual.fills), 14)
        self.assertLess(dual.snapshots[-1].equity, maker.snapshots[-1].equity)

    def test_trend_equity_worse_than_neutral(self) -> None:
        maker = run_path(NeutralMaker(), TREND_PATH)
        dual = run_path(DualOpen(), TREND_PATH)
        self.assertLess(dual.snapshots[-1].equity, maker.snapshots[-1].equity)
        # dual leftover shorts grow faster than one-per-level grid shorts
        self.assertGreater(dual.short_qty(), maker.short_qty())


class FeeIdentityTests(unittest.TestCase):
    def test_one_grid_gross_matches_price_step(self) -> None:
        e = NeutralMaker()
        grid = e.qty * (e.px(1) - e.px(0))
        expected = DEFAULT_QTY * DEFAULT_P0 * 0.0001
        self.assertAlmostEqual(grid, expected)


if __name__ == "__main__":
    unittest.main()
