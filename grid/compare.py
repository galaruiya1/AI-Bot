#!/usr/bin/env python3
"""Neutral Maker grid vs dual-open hedge grid.

Rules and the fee-inclusive P&L comparison live in this module so they can be
executed, not just described.

Grid geometry
-------------
Price levels are integers. Level 0 is the start price P0. One step is
``step_bp`` basis points (default 1bp = 0.01%), so

    price(level) = P0 * (1 + level * step_bp / 10_000)

Shared path (covers the three cases: up, retrace to origin, down)
-----------------------------------------------------------------
    0 → +1 → 0 → -1 → 0

  * 0 → +1          price up one grid
  * +1 → 0          up then back to the first fill price
  * 0 → -1          price down one grid
  * -1 → 0          down then back to origin

A trend path is also reported: 0 → +1 → +2 → +3 → +4.

Fees (USDT-M perp, regular-tier defaults)
-----------------------------------------
  * Maker  2.0 bp  (0.020%)
  * Taker  4.0 bp  (0.040%)

Neutral Maker fills as maker. Dual-open hits the market at the current level,
so it pays taker. A third run charges dual-open maker fees only, to isolate
the extra trades from the fee tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Side = Literal["buy", "sell"]
PosSide = Literal["long", "short"]
Purpose = Literal["open_long", "open_short", "close_long", "close_short"]

MAKER_FEE = 0.0002
TAKER_FEE = 0.0004
DEFAULT_P0 = 100_000.0
DEFAULT_QTY = 0.01  # BTC; notional at P0 = 1_000 USDT
DEFAULT_STEP_BP = 1.0


def price_of(p0: float, step_bp: float, level: int) -> float:
    return p0 * (1.0 + level * step_bp / 10_000.0)


def bp(notional: float, usdt: float) -> float:
    """USDT P&L expressed in bp of one-leg start notional."""
    if notional == 0:
        return 0.0
    return usdt / notional * 10_000.0


@dataclass
class Order:
    side: Side
    level: int
    purpose: Purpose
    qty: float


@dataclass
class Position:
    side: PosSide
    level: int
    qty: float
    entry: float


@dataclass
class Fill:
    step: int
    strategy: str
    side: Side
    purpose: Purpose
    level: int
    price: float
    qty: float
    fee: float
    maker: bool
    note: str


@dataclass
class Snapshot:
    name: str
    level: int
    price: float
    long_qty: float
    short_qty: float
    realized: float
    unrealized: float
    fees: float
    equity: float
    fills_so_far: int
    notes: str


@dataclass
class Engine:
    name: str
    p0: float = DEFAULT_P0
    qty: float = DEFAULT_QTY
    step_bp: float = DEFAULT_STEP_BP
    maker_fee: float = MAKER_FEE
    taker_fee: float = TAKER_FEE
    longs: list[Position] = field(default_factory=list)
    shorts: list[Position] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    snapshots: list[Snapshot] = field(default_factory=list)
    realized: float = 0.0
    fees: float = 0.0
    last_level: int = 0
    clock: int = 0

    @property
    def start_notional(self) -> float:
        return self.qty * self.p0

    def px(self, level: int) -> float:
        return price_of(self.p0, self.step_bp, level)

    def long_qty(self) -> float:
        return sum(p.qty for p in self.longs)

    def short_qty(self) -> float:
        return sum(p.qty for p in self.shorts)

    def unrealized(self, mark_level: int) -> float:
        mark = self.px(mark_level)
        u = 0.0
        for p in self.longs:
            u += p.qty * (mark - p.entry)
        for p in self.shorts:
            u += p.qty * (p.entry - mark)
        return u

    def equity(self, mark_level: int) -> float:
        return self.realized + self.unrealized(mark_level) - self.fees

    def _fill(
        self,
        side: Side,
        purpose: Purpose,
        level: int,
        maker: bool,
        note: str,
    ) -> None:
        price = self.px(level)
        rate = self.maker_fee if maker else self.taker_fee
        fee = rate * self.qty * price
        self.fees += fee
        self.fills.append(
            Fill(
                step=self.clock,
                strategy=self.name,
                side=side,
                purpose=purpose,
                level=level,
                price=price,
                qty=self.qty,
                fee=fee,
                maker=maker,
                note=note,
            )
        )

    def open_long(self, level: int, maker: bool, note: str) -> None:
        self._fill("buy", "open_long", level, maker, note)
        self.longs.append(
            Position("long", level, self.qty, self.px(level))
        )

    def open_short(self, level: int, maker: bool, note: str) -> None:
        self._fill("sell", "open_short", level, maker, note)
        self.shorts.append(
            Position("short", level, self.qty, self.px(level))
        )

    def close_long_at(self, entry_level: int, exit_level: int, maker: bool, note: str) -> bool:
        idx = next((i for i, p in enumerate(self.longs) if p.level == entry_level), None)
        if idx is None:
            return False
        pos = self.longs.pop(idx)
        exit_px = self.px(exit_level)
        self.realized += pos.qty * (exit_px - pos.entry)
        self._fill("sell", "close_long", exit_level, maker, note)
        return True

    def close_short_at(self, entry_level: int, exit_level: int, maker: bool, note: str) -> bool:
        idx = next((i for i, p in enumerate(self.shorts) if p.level == entry_level), None)
        if idx is None:
            return False
        pos = self.shorts.pop(idx)
        exit_px = self.px(exit_level)
        self.realized += pos.qty * (pos.entry - exit_px)
        self._fill("buy", "close_short", exit_level, maker, note)
        return True

    def snap(self, level: int, notes: str) -> Snapshot:
        s = Snapshot(
            name=self.name,
            level=level,
            price=self.px(level),
            long_qty=self.long_qty(),
            short_qty=self.short_qty(),
            realized=self.realized,
            unrealized=self.unrealized(level),
            fees=self.fees,
            equity=self.equity(level),
            fills_so_far=len(self.fills),
            notes=notes,
        )
        self.snapshots.append(s)
        return s

    def inventory_desc(self) -> str:
        longs = ",".join(str(p.level) for p in self.longs) or "-"
        shorts = ",".join(str(p.level) for p in self.shorts) or "-"
        return f"L[{longs}] S[{shorts}]"


# ---------------------------------------------------------------------------
# Neutral Maker grid
# ---------------------------------------------------------------------------
#
# 状态
#   current : 当前价格所在格
#   longs / shorts : 已成交仓位（记录开仓格）
#   orders : 只挂当前格邻格的 Maker 限价单
#
# 初始（格 0，空仓）
#   买开多 @ -1
#   卖开空 @ +1
#   现价不成交、不锁仓
#
# 成交后重挂（一层邻格 + 减仓止盈）
#   每笔多仓在 开仓格+1 挂卖平多
#   每笔空仓在 开仓格-1 挂买平空
#   若该价位还没有买单，则在 current-1 挂买开多
#   若该价位还没有卖单，则在 current+1 挂卖开空
#
# 三条路径
#   上涨 1 格     卖开空成交 → 持有空 1 份，下方挂买平空
#   回撤到起点    买平空成交 → 空单止盈 1 格，恢复空仓双边挂单
#   下跌 1 格     买开多成交 → 持有多 1 份，上方挂卖平多
#
class NeutralMaker(Engine):
    def __init__(self, **kwargs) -> None:
        super().__init__(name=kwargs.pop("name", "neutral_maker"), **kwargs)

    def start(self) -> None:
        self.last_level = 0
        self._sync_quotes(0)
        self.snap(0, "空仓，挂买@-1 / 卖@+1")

    def _sync_quotes(self, current: int) -> None:
        self.orders.clear()
        occupied_buy: set[int] = set()
        occupied_sell: set[int] = set()
        for pos in self.longs:
            lvl = pos.level + 1
            self.orders.append(Order("sell", lvl, "close_long", self.qty))
            occupied_sell.add(lvl)
        for pos in self.shorts:
            lvl = pos.level - 1
            self.orders.append(Order("buy", lvl, "close_short", self.qty))
            occupied_buy.add(lvl)
        buy_lvl = current - 1
        sell_lvl = current + 1
        if buy_lvl not in occupied_buy:
            self.orders.append(Order("buy", buy_lvl, "open_long", self.qty))
        if sell_lvl not in occupied_sell:
            self.orders.append(Order("sell", sell_lvl, "open_short", self.qty))

    def on_level(self, level: int) -> None:
        self.clock += 1
        due = [o for o in self.orders if o.level == level]
        notes: list[str] = []
        for order in due:
            if order.purpose == "open_long":
                self.open_long(level, True, "Maker 买开多")
                notes.append("买开多")
            elif order.purpose == "open_short":
                self.open_short(level, True, "Maker 卖开空")
                notes.append("卖开空")
            elif order.purpose == "close_long":
                # FIFO among longs whose TP is this level (entry = level - 1)
                ok = self.close_long_at(level - 1, level, True, "Maker 卖平多")
                notes.append("卖平多" if ok else "卖平多(未找到仓)")
            elif order.purpose == "close_short":
                ok = self.close_short_at(level + 1, level, True, "Maker 买平空")
                notes.append("买平空" if ok else "买平空(未找到仓)")
        self.last_level = level
        self._sync_quotes(level)
        label = "+".join(notes) if notes else "无成交"
        self.snap(level, f"{label} | {self.inventory_desc()}")


# ---------------------------------------------------------------------------
# Dual-open (the current idea): every arrival opens both sides, then
# closes the previous winning leg. Fills are taker unless maker_mode=True.
# ---------------------------------------------------------------------------
#
# 初始（格 0）
#   市价开多 + 市价开空，等量锁仓
#
# 价格到达新格 L（相对上一格 prev）
#   1. 在 L 再开一对多空
#   2. 若 L > prev：平掉在 prev 开的那笔多（上涨止盈多）
#   3. 若 L < prev：平掉在 prev 开的那笔空（下跌止盈空）
#
# 先涨后跌回起点：+1 时平掉 0 的多；回到 0 时平掉 +1 的空。
#
class DualOpen(Engine):
    def __init__(self, maker_mode: bool = False, **kwargs) -> None:
        name = kwargs.pop("name", None)
        super().__init__(
            name=name or ("dual_open_maker" if maker_mode else "dual_open_taker"),
            **kwargs,
        )
        self.maker_mode = maker_mode

    def start(self) -> None:
        m = self.maker_mode
        self.open_long(0, m, "起点双开·多")
        self.open_short(0, m, "起点双开·空")
        self.last_level = 0
        self.snap(0, f"起点锁仓 | {self.inventory_desc()}")

    def on_level(self, level: int) -> None:
        if level == self.last_level:
            return
        self.clock += 1
        prev = self.last_level
        m = self.maker_mode
        self.open_long(level, m, f"格{level}双开·多")
        self.open_short(level, m, f"格{level}双开·空")
        if level > prev:
            ok = self.close_long_at(prev, level, m, f"上涨，平格{prev}的多")
            action = f"上涨：平多@{prev}" + ("" if ok else "(未找到)")
        else:
            ok = self.close_short_at(prev, level, m, f"下跌，平格{prev}的空")
            action = f"下跌：平空@{prev}" + ("" if ok else "(未找到)")
        self.last_level = level
        self.snap(level, f"{action} | {self.inventory_desc()}")


RANGE_PATH = [0, 1, 0, -1, 0]
TREND_PATH = [0, 1, 2, 3, 4]
RANGE_LABELS = {
    0: "起点",
    1: "上涨 1 格",
    2: "涨后回到起点",
    3: "下跌 1 格",
    4: "跌后回到起点",
}
TREND_LABELS = {
    0: "起点",
    1: "涨到 +1",
    2: "涨到 +2",
    3: "涨到 +3",
    4: "涨到 +4",
}


def run_path(engine: Engine, path: list[int]) -> Engine:
    engine.start()
    for level in path[1:]:
        engine.on_level(level)
    return engine


def _fmt_usdt(x: float) -> str:
    return f"{x:+.4f}"


def _fmt_bp(x: float) -> str:
    return f"{x:+.2f}bp"


def _table(engines: list[Engine], labels: dict[int, str], notional: float) -> str:
    names = [e.name for e in engines]
    header = ["步", "行情", *[n for n in names]]
    lines = [" | ".join(header), " | ".join(["---"] * len(header))]
    n_steps = len(engines[0].snapshots)
    for i in range(n_steps):
        row = [str(i), labels.get(i, f"s{i}")]
        for e in engines:
            s = e.snapshots[i]
            eq = _fmt_usdt(s.equity)
            eq_bp = _fmt_bp(bp(notional, s.equity))
            row.append(
                f"权益 {eq} ({eq_bp}); "
                f"费 {s.fees:.4f}; "
                f"多{s.long_qty:.2f}/空{s.short_qty:.2f}; "
                f"成交{s.fills_so_far}; {s.notes}"
            )
        lines.append(" | ".join(row))
    return "\n".join(lines)


def _final_block(e: Engine) -> str:
    last = e.snapshots[-1]
    n = e.start_notional
    return (
        f"{e.name}\n"
        f"  fills={len(e.fills)}  long={last.long_qty:.4f}  short={last.short_qty:.4f}\n"
        f"  realized={last.realized:+.6f}  unrealized={last.unrealized:+.6f}  fees={last.fees:.6f}\n"
        f"  equity={last.equity:+.6f} USDT  ({bp(n, last.equity):+.2f} bp of one-leg notional {n:.0f})\n"
        f"  inventory {e.inventory_desc()}"
    )


def compare(
    path: list[int],
    labels: dict[int, str],
    title: str,
    p0: float = DEFAULT_P0,
    qty: float = DEFAULT_QTY,
    step_bp: float = DEFAULT_STEP_BP,
) -> str:
    kwargs = dict(p0=p0, qty=qty, step_bp=step_bp)
    engines = [
        run_path(NeutralMaker(**kwargs), path),
        run_path(DualOpen(maker_mode=False, **kwargs), path),
        run_path(DualOpen(maker_mode=True, **kwargs), path),
    ]
    notional = qty * p0
    parts = [
        title,
        f"P0={p0:.0f}  qty={qty}  step={step_bp}bp  "
        f"one-leg notional={notional:.0f} USDT  "
        f"maker={MAKER_FEE*1e4:.1f}bp  taker={TAKER_FEE*1e4:.1f}bp",
        "",
        _table(engines, labels, notional),
        "",
    ]
    for e in engines:
        parts.append(_final_block(e))
        parts.append("")
    parts.append("Fill log")
    for e in engines:
        parts.append(f"-- {e.name} --")
        for f in e.fills:
            kind = "M" if f.maker else "T"
            parts.append(
                f"  t{f.step} {kind} {f.purpose:11} lvl={f.level:+d} "
                f"px={f.price:.4f} fee={f.fee:.4f}  {f.note}"
            )
        parts.append("")
    return "\n".join(parts)


def main() -> None:
    print(
        compare(
            RANGE_PATH,
            RANGE_LABELS,
            "=== Path R: 0 → +1 → 0 → -1 → 0  (three user cases on one tape) ===",
        )
    )
    print(
        compare(
            TREND_PATH,
            TREND_LABELS,
            "=== Path T: 0 → +1 → +2 → +3 → +4  (one-way trend) ===",
        )
    )
    print(
        compare(
            RANGE_PATH,
            RANGE_LABELS,
            "=== Path R at 50bp step (same tape, viable spacing) ===",
            step_bp=50.0,
        )
    )


if __name__ == "__main__":
    main()
