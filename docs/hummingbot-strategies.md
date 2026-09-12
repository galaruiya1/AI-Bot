# Hummingbot 策略全目录

来源：[hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) `master`。路径均为仓库内相对路径。

Hummingbot 把策略分成三层积木：

| 组件 | 作用 | 适合 |
| --- | --- | --- |
| **Executor** | 一次交易任务（开仓、网格、DCA、套利、LP） | 单次任务 / API 调用 |
| **Script** | 单个 Python 文件，逻辑全在一起 | 学习、原型、单交易对 |
| **Controller** | 可复用子策略，由 `v2_with_controllers.py` 加载，可多实例并行 | 生产、多交易对、可热更新参数 |

官方推荐新策略用 V2。V1 在 `hummingbot/strategy/`，仍能跑，但不再作为主开发方向。

启动约定：

```bash
# V2 script
hbot create simple_pmm --name conf_paper.yml --set exchange=binance_paper_trade
hbot start conf_paper.yml

# V2 controller（hbot 会自动生成 loader）
hbot create pmm_simple --name conf_eth.yml --set connector_name=binance --set trading_pair=ETH-USDT
hbot start conf_eth.yml

# 交互客户端等价命令
create --v2-config <script>
create --controller-config <category.name>
start --v2 <config.yml>
```

Controller 名称是 `controllers/` 下的点分路径，例如 `directional_trading.bollinger_v1`、`market_making.pmm_simple`。

---

## 1. V2 Controllers（推荐）

代码根目录：[`controllers/`](https://github.com/hummingbot/hummingbot/tree/master/controllers)

基类在 `hummingbot/strategy_v2/controllers/`：

- `controller_base.py`
- `directional_trading_controller_base.py`（信号 `1` 开多 / `-1` 开空）
- `market_making_controller_base.py`

### 1.1 趋势 / 方向性 `controllers/directional_trading/`

| 名称 | 文件 | 逻辑摘要 |
| --- | --- | --- |
| `bollinger_v1` | [bollinger_v1.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/directional_trading/bollinger_v1.py) | Bollinger Band Percent（BBP）。BBP 低于 `bb_long_threshold` 做多，高于 `bb_short_threshold` 做空。默认 K 线 `3m`，BB 长度 100、标准差 2。 |
| `bollinger_v2` | [bollinger_v2.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/directional_trading/bollinger_v2.py) | 布林带升级版，使用 TA-Lib 布林带与更长的 K 线窗口。 |
| `macd_bb_v1` | [macd_bb_v1.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/directional_trading/macd_bb_v1.py) | MACD + 布林带共振：默认 MACD 21/42/9，BB 同 V1。 |
| `supertrend_v1` | [supertrend_v1.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/directional_trading/supertrend_v1.py) | SuperTrend（默认 length=20, multiplier=4）加百分比阈值过滤。 |
| `dman_v3` | [dman_v3.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/directional_trading/dman_v3.py) | 均值回归 + 网格式 DCA。布林带定方向，用 `DCAExecutor` 分批建仓，带三重屏障（止盈/止损/时间/移动止盈）。 |
| `bollingrid` | [bollingrid.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/directional_trading/bollingrid.py) | 布林带信号驱动 `GridExecutor`：网格起止价、限价由 BB 宽度系数决定。 |
| `ai_livestream` | [ai_livestream.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/directional_trading/ai_livestream.py) | **外部 ML 信号驱动**。订阅 MQTT 主题 `hbot/predictions/{pair}/ML_SIGNALS`，按 `long_threshold` / `short_threshold` 开仓。适合接 Condor 或自建模型。 |

方向性策略共同参数（基类）：交易所、交易对、杠杆、仓位执行器的止损/止盈/时间限制/移动止盈、下单金额、冷却时间。

### 1.2 做市 `controllers/market_making/`

| 名称 | 文件 | 逻辑摘要 |
| --- | --- | --- |
| `pmm_simple` | [pmm_simple.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/market_making/pmm_simple.py) | 最简纯做市。买卖价差 + 多层挂单，用 `PositionExecutor` + 三重屏障管风险。入门首选。 |
| `pmm_dynamic` | [pmm_dynamic.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/market_making/pmm_dynamic.py) | 动态做市：MACD 平移中间价，NATR 把价差换成波动率倍数（如 `1,2,4`）。 |
| `dman_maker_v2` | [dman_maker_v2.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/market_making/dman_maker_v2.py) | 做市 + DCA。每层用 `DCAExecutor`，默认价差 `0.01,0.02,0.04,0.08`，金额按比例加码。 |

### 1.3 通用 `controllers/generic/`

| 名称 | 文件 | 逻辑摘要 |
| --- | --- | --- |
| `pmm_v1` | [pmm_v1.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/generic/pmm_v1.py) | 把遗留 `pure_market_making` 迁到 V2：多层价差/数量、库存倾斜、刷新容差、静态/移动价格带。 |
| `pmm_mister` | [pmm_mister.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/generic/pmm_mister.py) | 官方 README 的实盘示例。高级 PMM：库存目标区间、挂单冷却、价格距离容忍、盈亏平衡感知、全局止盈止损。参数可热更新。 |
| `grid_strike` | [grid_strike.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/generic/grid_strike.py) | 单交易对网格。配置 `start_price` / `end_price` / `limit_price`，在区间内用 `GridExecutor` 挂网。 |
| `multi_grid_strike` | [multi_grid_strike.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/generic/multi_grid_strike.py) | 多组网格并行。 |
| `quantum_grid_allocator` | [quantum_grid_allocator.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/generic/quantum_grid_allocator.py) | 组合网格分配：按 `portfolio_allocation` 给多资产分配资金，布林带可动态调网格宽度，含多空阈值与对冲比。 |
| `arbitrage_controller` | [arbitrage_controller.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/generic/arbitrage_controller.py) | 跨所套利（CEX ↔ AMM，例如 Binance vs Jupiter）。`ArbitrageExecutor`，最小利润率、执行器不平衡上限。 |
| `xemm_multiple_levels` | [xemm_multiple_levels.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/generic/xemm_multiple_levels.py) | 跨所做市（XEMM）多层：maker 挂限价，taker 对冲成交。每层有目标利润率与数量。 |
| `stat_arb` | [stat_arb.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/generic/stat_arb.py) | 统计套利。对两个协整标的做线性回归，用 z-score 进出场（主腿 + 对冲腿）。 |
| `hedge_asset` | [hedge_asset.py](https://github.com/hummingbot/hummingbot/blob/master/controllers/generic/hedge_asset.py) | 现货库存对冲：跟踪现货余额，在永续上维持 `spot × hedge_ratio` 空头，带最小名义值和冷却，避免过度交易。 |
| `lp_rebalancer` | [lp_rebalancer/](https://github.com/hummingbot/hummingbot/tree/master/controllers/generic/lp_rebalancer) | 集中流动性（CLMM）自动再平衡。价格越界后用 `LPExecutor` 重建仓位；支持 Meteora / Orca / Raydium，不足余额可 autoswap。 |

### 1.4 教学示例 `controllers/generic/examples/`

| 文件 | 用途 |
| --- | --- |
| `basic_order_example.py` | 基础下单 |
| `basic_order_open_close_example.py` | 开平仓 |
| `buy_three_times_example.py` | 连续买入 |
| `candles_data_controller.py` | K 线数据 |
| `full_trading_example.py` | 完整交易流 |
| `liquidations_monitor_controller.py` | 清算监控 |
| `market_status_controller.py` | 市场状态 |
| `price_monitor_controller.py` | 价格监控 |

---

## 2. V2 Scripts

代码根目录：[`scripts/`](https://github.com/hummingbot/hummingbot/tree/master/scripts)

新脚本应继承 `StrategyV2Base`（`hummingbot/strategy/strategy_v2_base.py`）。

### 可交易脚本

| 脚本 | 文件 | 逻辑摘要 |
| --- | --- | --- |
| `simple_pmm` | [simple_pmm.py](https://github.com/hummingbot/hummingbot/blob/master/scripts/simple_pmm.py) | 入门做市：中间价两侧挂买单/卖单，到期撤单重挂。纸交易默认脚本。 |
| `simple_vwap` | [simple_vwap.py](https://github.com/hummingbot/hummingbot/blob/master/scripts/simple_vwap.py) | VWAP 拆单：按盘口成交量百分比分批买入或卖出，限制价格偏离。 |
| `simple_xemm` | [simple_xemm.py](https://github.com/hummingbot/hummingbot/blob/master/scripts/simple_xemm.py) | 跨所做市原型：maker 挂单，taker 对冲；目标/最小利润率、订单最长存活时间。 |
| `v2_funding_rate_arb` | [v2_funding_rate_arb.py](https://github.com/hummingbot/hummingbot/blob/master/scripts/v2_funding_rate_arb.py) | 资金费率套利：比较多家永续（如 Hyperliquid vs Binance）资金费率，费率差够大则对锁仓位。 |
| `v2_with_controllers` | [v2_with_controllers.py](https://github.com/hummingbot/hummingbot/blob/master/scripts/v2_with_controllers.py) | Controller 加载器。可同时跑多个 controller，支持全局/单 controller 回撤限制和 cash out。 |

### 数据 / 工具脚本

| 脚本 | 用途 |
| --- | --- |
| `screener_volatility.py` | 波动率筛票：NATR、布林带宽度，定期输出 Top N |
| `candles_example.py` | 拉取 K 线 |
| `download_order_book_and_trades.py` | 下载盘口与成交 |
| `amm_data_feed_example.py` | AMM 数据 |
| `log_price_example.py` | 打价格日志 |
| `format_status_example.py` | 自定义 status |
| `external_events_example.py` | 外部事件 |
| `xrpl_arb_example.py` / `xrpl_liquidity_example.py` | XRPL 套利 / 流动性 |
| `backtest_bollinger_v2.py` / `backtest_grid_strike.py` / `backtest_pmm_mister.py` | 对应策略回测入口 |

---

## 3. V2 Executors

代码根目录：[`hummingbot/strategy_v2/executors/`](https://github.com/hummingbot/hummingbot/tree/master/hummingbot/strategy_v2/executors)

| Executor | 做什么 |
| --- | --- |
| `order_executor` | 下并跟踪单笔订单 |
| `position_executor` | 开仓 + 三重屏障（止盈、止损、时间、移动止盈） |
| `dca_executor` | 分批加仓 |
| `twap_executor` | 时间加权拆单 |
| `grid_executor` | 网格挂单与回收 |
| `arbitrage_executor` | 两边同时吃价差 |
| `xemm_executor` | maker 成交后 taker 对冲 |
| `lp_executor` | 链上 LP 仓位开关与再平衡 |
| `executor_orchestrator` | 调度上述执行器 |

---

## 4. V1 遗留策略

代码根目录：[`hummingbot/strategy/`](https://github.com/hummingbot/hummingbot/tree/master/hummingbot/strategy)

官方说明：仍随月度版本发布，Foundation 不再主动维护。交互客户端用 `create`（不加 `--v2-config`）生成配置。

| 策略 | 目录 | 说明 |
| --- | --- | --- |
| `pure_market_making` | `pure_market_making/` | 原始单交易对做市。V2 对应 `pmm_v1` / `pmm_simple`。 |
| `avellaneda_market_making` | `avellaneda_market_making/` | Avellaneda–Stoikov 最优做市。 |
| `perpetual_market_making` | `perpetual_market_making/` | 永续合约做市。 |
| `cross_exchange_market_making` | `cross_exchange_market_making/` | 跨所做市，另一所对冲库存。V2 对应 `simple_xemm` / `xemm_multiple_levels`。 |
| `cross_exchange_mining` | `cross_exchange_mining/` | 社区改版跨所做市。 |
| `amm_arb` | `amm_arb/` | CEX 与 AMM DEX 价差套利。V2 对应 `arbitrage_controller`。 |
| `spot_perpetual_arbitrage` | `spot_perpetual_arbitrage/` | 现货 vs 永续基差套利。 |
| `hedge` | `hedge/` | 用永续对冲现货库存。V2 对应 `hedge_asset`。 |
| `liquidity_mining` | `liquidity_mining/` | 用单一 base/quote 给多交易对提供流动性。 |

---

## 5. 按交易想法选型

| 你想做的事 | 优先看 |
| --- | --- |
| 第一次跑起来（纸交易） | `simple_pmm` |
| 实盘单对做市 | `pmm_mister` 或 `pmm_simple` |
| 波动率自适应做市 | `pmm_dynamic` |
| 经典多层做市 + 库存倾斜 | `pmm_v1`（或 V1 `pure_market_making`） |
| 趋势跟随（指标） | `bollinger_v1` / `macd_bb_v1` / `supertrend_v1` |
| 接自己的 AI/ML 信号 | `ai_livestream` + [Condor](https://github.com/hummingbot/condor) |
| 均值回归分批建仓 | `dman_v3`、`dman_maker_v2` |
| 网格 | `grid_strike`、`bollingrid`、`quantum_grid_allocator` |
| 跨所吃价差 | `arbitrage_controller`、`amm_arb` |
| Maker 挂单 + 另一所对冲 | `simple_xemm`、`xemm_multiple_levels` |
| 资金费率 | `v2_funding_rate_arb` |
| 协整配对 | `stat_arb` |
| 现货库存对冲 | `hedge_asset` |
| 链上 LP | `lp_rebalancer` |
| 大单拆成 VWAP | `simple_vwap` |
| 选波动大的币 | `screener_volatility` |

---

## 6. 源码地图

```
hummingbot/hummingbot
├── controllers/                    # V2 策略控制器（用户会改这里）
│   ├── directional_trading/
│   ├── market_making/
│   └── generic/                    # 含 lp_rebalancer、examples
├── scripts/                        # V2 脚本入口
├── hummingbot/
│   ├── strategy/                   # V1 模板 + StrategyV2Base
│   └── strategy_v2/
│       ├── controllers/            # 基类
│       ├── executors/              # 执行器
│       ├── backtesting/
│       └── models/
└── hummingbot/cli/README.md        # hbot 命令说明
```

相关仓库：

- 主仓：[hummingbot/hummingbot](https://github.com/hummingbot/hummingbot)
- AI 编排：[hummingbot/condor](https://github.com/hummingbot/condor)
- 文档：[hummingbot.org/strategies](https://hummingbot.org/strategies/)
