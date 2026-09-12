"""BTC-oriented high-frequency wrapper around stock pmm_mister.

Drop this file into hummingbot/controllers/generic/. It keeps inventory, hanging
orders, and global TP/SL from PMMister, and changes quoting to tick units with
optional best-bid/ask join.

tick_mode is always the intended mode here:
- buy_spreads / sell_spreads are tick offsets (1 = one min_price_increment)
- price_distance_tolerance / refresh_tolerance are also ticks
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import Field, field_validator

from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction
from hummingbot.strategy_v2.utils.common import parse_enum_value

from controllers.generic.pmm_mister import PMMister, PMMisterConfig


class PMMisterHFTConfig(PMMisterConfig):
    controller_name: str = "pmm_mister_hft"
    connector_name: str = Field(default="binance_perpetual")
    trading_pair: str = Field(default="BTC-USDT")

    # Quote from mid, or from the live bid/ask (HFT default).
    price_source: str = Field(default="best_bid_ask", json_schema_extra={"is_updatable": True})
    # If true, spread N sits (N-1) ticks behind the touch so 1 tick joins best bid/ask.
    join_touch: bool = Field(default=True, json_schema_extra={"is_updatable": True})

    tick_mode: bool = Field(default=True, json_schema_extra={"is_updatable": True})
    buy_spreads: list = Field(default="1", json_schema_extra={"is_updatable": True})
    sell_spreads: list = Field(default="1", json_schema_extra={"is_updatable": True})
    buy_amounts_pct: list = Field(default="1", json_schema_extra={"is_updatable": True})
    sell_amounts_pct: list = Field(default="1", json_schema_extra={"is_updatable": True})

    executor_refresh_time: int = Field(default=3, json_schema_extra={"is_updatable": True})
    buy_cooldown_time: int = Field(default=4, json_schema_extra={"is_updatable": True})
    sell_cooldown_time: int = Field(default=4, json_schema_extra={"is_updatable": True})
    buy_position_effectivization_time: int = Field(default=15, json_schema_extra={"is_updatable": True})
    sell_position_effectivization_time: int = Field(default=15, json_schema_extra={"is_updatable": True})

    # Tick units while tick_mode is true.
    price_distance_tolerance: Decimal = Field(default=Decimal("1"), json_schema_extra={"is_updatable": True})
    refresh_tolerance: Decimal = Field(default=Decimal("2"), json_schema_extra={"is_updatable": True})
    tolerance_scaling: Decimal = Field(default=Decimal("1.5"), json_schema_extra={"is_updatable": True})

    max_active_executors_by_level: Optional[int] = Field(default=1, json_schema_extra={"is_updatable": True})
    min_skew: Decimal = Field(default=Decimal("0.25"), json_schema_extra={"is_updatable": True})
    position_profit_protection: bool = Field(default=True, json_schema_extra={"is_updatable": True})
    # Each open/close clip in quote (USDT notional, before leverage).
    order_notional_quote: Decimal = Field(default=Decimal("800"), json_schema_extra={"is_updatable": True})
    take_profit: Optional[Decimal] = Field(default=Decimal("0.00015"), json_schema_extra={"is_updatable": True})
    stop_loss: Optional[Decimal] = Field(default=Decimal("0.0005"), json_schema_extra={"is_updatable": True})
    time_limit: Optional[int] = Field(default=120, json_schema_extra={"is_updatable": True})
    take_profit_order_type: Optional[OrderType] = Field(
        default=OrderType.LIMIT_MAKER, json_schema_extra={"is_updatable": True}
    )
    open_order_type: Optional[OrderType] = Field(
        default=OrderType.LIMIT_MAKER, json_schema_extra={"is_updatable": True}
    )

    leverage: int = Field(default=20, json_schema_extra={"is_updatable": True})
    position_mode: PositionMode = Field(default=PositionMode.HEDGE)
    position_side: TradeType = Field(default="BUY")

    global_tp_enabled: bool = Field(default=True, json_schema_extra={"is_updatable": True})
    global_sl_enabled: bool = Field(default=True, json_schema_extra={"is_updatable": True})
    global_take_profit: Decimal = Field(default=Decimal("0.008"), json_schema_extra={"is_updatable": True})
    global_stop_loss: Decimal = Field(default=Decimal("0.015"), json_schema_extra={"is_updatable": True})
    global_tp_activation_from: str = Field(default="min_base", json_schema_extra={"is_updatable": True})
    global_sl_activation_from: str = Field(default="target_base", json_schema_extra={"is_updatable": True})

    target_base_pct: Decimal = Field(default=Decimal("0.5"), json_schema_extra={"is_updatable": True})
    min_base_pct: Decimal = Field(default=Decimal("0.25"), json_schema_extra={"is_updatable": True})
    max_base_pct: Decimal = Field(default=Decimal("0.70"), json_schema_extra={"is_updatable": True})
    portfolio_allocation: Decimal = Field(default=Decimal("1"), json_schema_extra={"is_updatable": True})

    @field_validator("price_source", mode="before")
    @classmethod
    def validate_price_source(cls, v):
        value = str(v).lower()
        if value not in {"mid", "best_bid_ask"}:
            raise ValueError("price_source must be mid or best_bid_ask")
        return value

    def get_spreads_and_amounts_in_quote(self, trade_type: TradeType):
        """Each clip is order_notional_quote USDT, independent of the 50/50 parent split."""
        spreads = self.buy_spreads if trade_type == TradeType.BUY else self.sell_spreads
        return spreads, [self.order_notional_quote for _ in spreads]

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        open_order_type = self.open_order_type if isinstance(self.open_order_type, OrderType) else OrderType.LIMIT_MAKER
        take_profit_order_type = (
            self.take_profit_order_type if isinstance(self.take_profit_order_type, OrderType) else OrderType.LIMIT_MAKER
        )
        return TripleBarrierConfig(
            take_profit=self.take_profit,
            stop_loss=self.stop_loss,
            time_limit=self.time_limit,
            trailing_stop=None,
            open_order_type=open_order_type,
            take_profit_order_type=take_profit_order_type,
            stop_loss_order_type=OrderType.MARKET,
            time_limit_order_type=OrderType.MARKET,
        )

    @field_validator("position_mode", mode="before")
    @classmethod
    def validate_position_mode(cls, v) -> PositionMode:
        return parse_enum_value(PositionMode, v, "position_mode")


class PMMisterHFT(PMMister):
    """pmm_mister with tick quoting, top-of-book prices, and tick-based refresh."""

    def __init__(self, config: PMMisterHFTConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

    def _tick_size(self) -> Optional[Decimal]:
        try:
            rules = self.market_data_provider.get_trading_rules(
                self.config.connector_name, self.config.trading_pair
            )
            tick = Decimal(str(rules.min_price_increment))
            return tick if tick > 0 else None
        except Exception:
            return None

    def _safe_price(self, price_type: PriceType) -> Optional[Decimal]:
        try:
            price = self.market_data_provider.get_price_by_type(
                self.config.connector_name, self.config.trading_pair, price_type
            )
            if price is None or price <= 0:
                return None
            return Decimal(str(price))
        except Exception:
            return None

    def _ticks_to_pct(self, ticks: Decimal, reference_price: Decimal, tick: Decimal) -> Decimal:
        return (Decimal(str(ticks)) * tick) / reference_price

    async def update_processed_data(self):
        mid = self._safe_price(PriceType.MidPrice)
        best_bid = self._safe_price(PriceType.BestBid)
        best_ask = self._safe_price(PriceType.BestAsk)
        if mid is None or mid <= 0:
            mid = Decimal(str(self.processed_data.get("reference_price", Decimal("100"))))
            self.logger().warning("Invalid mid price, reusing previous reference")

        tick = self._tick_size()
        if self.config.tick_mode and tick is not None:
            spread_multiplier = tick / mid
        else:
            spread_multiplier = Decimal("1")

        quote_bid = best_bid if best_bid is not None else mid
        quote_ask = best_ask if best_ask is not None else mid
        if self.config.price_source == "mid":
            quote_bid = mid
            quote_ask = mid

        current_time = self.market_data_provider.time()
        self.price_history.append({"timestamp": current_time, "price": mid})
        if len(self.price_history) > self.max_price_history:
            self.price_history.pop(0)

        self.processed_data = {
            "reference_price": mid,
            "spread_multiplier": spread_multiplier,
            "tick_size": tick,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "quote_bid": quote_bid,
            "quote_ask": quote_ask,
        }

    def _apply_tick_tolerances(self):
        """Parent price-distance checks are percent; keep refresh_tolerance in ticks."""
        if not self.config.tick_mode:
            return None
        tick = self.processed_data.get("tick_size")
        ref = self.processed_data.get("reference_price")
        if tick is None or ref is None or ref <= 0:
            return None
        original = self.config.price_distance_tolerance
        self.config.price_distance_tolerance = self._ticks_to_pct(original, ref, tick)
        return original

    def _restore_tick_tolerances(self, original):
        if original is None:
            return
        self.config.price_distance_tolerance = original

    def _compute_executor_analysis(self):
        original = self._apply_tick_tolerances()
        try:
            super()._compute_executor_analysis()
        finally:
            self._restore_tick_tolerances(original)

    def should_refresh_executor_by_distance(self, executor_info, reference_price: Decimal) -> bool:
        tick = self.processed_data.get("tick_size")
        if not self.config.tick_mode or tick is None:
            return super().should_refresh_executor_by_distance(executor_info, reference_price)

        level_id = executor_info.custom_info.get("level_id", "")
        if not level_id or not hasattr(executor_info.config, "entry_price"):
            return False
        theoretical_price = self.calculate_theoretical_price(level_id, reference_price)
        if theoretical_price == 0:
            return False
        ticks_off = abs(executor_info.config.entry_price - theoretical_price) / tick
        level = self.get_level_from_level_id(level_id)
        return ticks_off > self.config.get_refresh_level_tolerance(level)

    def _quote_price(self, trade_type: TradeType, level: int) -> Decimal:
        mid = Decimal(self.processed_data["reference_price"])
        tick = self.processed_data.get("tick_size")
        spreads = self.config.buy_spreads if trade_type == TradeType.BUY else self.config.sell_spreads
        offset = Decimal(str(spreads[level]))

        if self.config.tick_mode and tick is not None:
            join = self.config.join_touch and self.config.price_source == "best_bid_ask"
            offset_ticks = max(offset - Decimal("1"), Decimal("0")) if join else offset
            if trade_type == TradeType.BUY:
                base = Decimal(self.processed_data.get("quote_bid") or mid)
                price = base - offset_ticks * tick
            else:
                base = Decimal(self.processed_data.get("quote_ask") or mid)
                price = base + offset_ticks * tick
        else:
            spread_in_pct = offset * Decimal(self.processed_data.get("spread_multiplier", 1))
            side_multiplier = Decimal("-1") if trade_type == TradeType.BUY else Decimal("1")
            price = mid * (Decimal("1") + side_multiplier * spread_in_pct)

        try:
            return self.market_data_provider.quantize_order_price(
                self.config.connector_name, self.config.trading_pair, price
            )
        except Exception:
            return price

    def calculate_theoretical_price(self, level_id: str, reference_price: Decimal) -> Decimal:
        trade_type = self.get_trade_type_from_level_id(level_id)
        level = self.get_level_from_level_id(level_id)
        spreads = self.config.buy_spreads if trade_type == TradeType.BUY else self.config.sell_spreads
        if level < 0 or level >= len(spreads):
            return reference_price
        return self._quote_price(trade_type, level)

    def create_actions_proposal(self) -> List[ExecutorAction]:
        create_actions = []
        levels_to_execute = self.processed_data.get("levels_to_execute", [])
        if not levels_to_execute:
            return create_actions

        _, buy_amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType.BUY)
        _, sell_amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType.SELL)
        buy_skew = self.processed_data["buy_skew"]
        sell_skew = self.processed_data["sell_skew"]

        for level_id in levels_to_execute:
            trade_type = self.get_trade_type_from_level_id(level_id)
            level = self.get_level_from_level_id(level_id)
            amount_quote = Decimal(buy_amounts_quote[level] if trade_type == TradeType.BUY else sell_amounts_quote[level])
            skew = buy_skew if trade_type == TradeType.BUY else sell_skew
            price = self._quote_price(trade_type, level)
            if price <= 0:
                continue

            amount = self.market_data_provider.quantize_order_amount(
                self.config.connector_name,
                self.config.trading_pair,
                (amount_quote / price) * skew,
            )
            if amount == Decimal("0"):
                self.logger().warning(f"The amount of the level {level_id} is 0. Skipping.")
                continue

            if self.config.position_profit_protection and not self._is_accumulation_side(trade_type):
                breakeven_price = self.processed_data.get("breakeven_price")
                if breakeven_price is not None and breakeven_price > 0:
                    if self.config.is_short and price > breakeven_price:
                        continue
                    if not self.config.is_short and price < breakeven_price:
                        continue

            executor_config = self.get_executor_config(level_id, price, amount)
            if executor_config is None:
                continue

            self.order_history.append({
                "timestamp": self.market_data_provider.time(),
                "price": price,
                "side": trade_type.name,
                "level_id": level_id,
                "action": "CREATE",
            })
            if len(self.order_history) > self.max_order_history:
                self.order_history.pop(0)

            create_actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=executor_config,
            ))

        return create_actions
