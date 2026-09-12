# pmm_mister_hft — BTC 高频改造

在官方 `pmm_mister` 上做秒级贴盘口改造，**先只跑 BTC-USDT**。不是微秒 HFT：Hummingbot 时钟最快 0.1 秒。

库存、挂起单、盈亏平衡保护、全局止盈止损仍用父类；改的是报价单位、刷新和冷却。

## 相对原版改了什么

| 项 | 原 `pmm_mister` | 本改造 |
| --- | --- | --- |
| 价差单位 | 比例（默认 5 bps ≈ BTC 上几千 tick） | **tick**（1 / 3 / 8） |
| 定价源 | 中间价 | **买一 / 卖一**，第 1 档加入队 |
| 刷新 | 30s 或 5 bps 偏离 | **3s 或 2 tick 偏离** |
| 冷却 / 计入库存 | 60s / 120s | **4s / 15s** |
| 每档挂单 | 最多 4 | **1**（少撤单、少叠仓） |
| `min_skew` | 1.0（库存 skew 等于关掉） | **0.25**（仓偏了会减量） |
| 止盈 | 1 bp，默认不算手续费 | **6 bp**，并打开全局 TP/SL |
| 时钟 | 默认 1s | **0.1s**（`conf_client.yml`） |

BTC-USDT 最小价位一般是 $0.01。1 tick 在 10 万附近约 0.01 bps，原版 5 bps 价差对高频来说过宽。

`take_profit` 必须大于 **2 × maker 费率**。Binance 现货挂单 0.02% 时往返 4 bps，6 bps 只留了薄利；有 BNB/VIP 零费率可以再收。费率更高就先把 `take_profit` 调到 0.001。

## 安装

在已经 `make install` 的 Hummingbot 源码树里：

```bash
HB=/path/to/hummingbot

cp strategies/pmm_mister_hft/pmm_mister_hft.py \
   $HB/controllers/generic/pmm_mister_hft.py

cp strategies/pmm_mister_hft/conf_pmm_mister_hft_btc_paper.yml \
   $HB/conf/controllers/

# 时钟改成 0.1s
# 编辑 $HB/conf/conf_client.yml ：tick_size: 0.1
# 或：hbot config tick_size 0.1
```

## 先纸交易

```bash
conda activate hummingbot
hbot config tick_size 0.1
hbot start conf_pmm_mister_hft_btc_paper.yml
hbot status
hbot logs -f
```

看三件事：买卖各三档是否贴在买一/卖一附近、3 秒内是否因价格偏离而刷新、库存是否在 35%–65%。

## 再小资金现货

```bash
cp strategies/pmm_mister_hft/conf_pmm_mister_hft_btc.yml $HB/conf/controllers/
hbot connect binance
hbot start conf_pmm_mister_hft_btc.yml
```

默认 `total_amount_quote: 200`、`portfolio_allocation: 0.5`，最内档大约 25 USDT，高于 BTC-USDT 最小名义金额。加资金只改这两个数，不要先加杠杆。

永续：把 `connector_name` 改成 `binance_perpetual`，`leverage` 从小倍数开始，`position_mode` 与账户一致。

## 运行中可热更新的旋钮

```bash
hbot config buy_spreads 1,2,5
hbot config executor_refresh_time 2
hbot config take_profit 0.001
hbot config manual_kill_switch true   # 停手，不关进程
```

## 档位含义（`join_touch: true`）

| 档 | ticks | 行为 |
| --- | ---: | --- |
| 0 | 1 | 加入买一 / 卖一 |
| 1 | 3 | 落后 2 tick |
| 2 | 8 | 落后 7 tick |

撤单过多：把 `refresh_tolerance` 调到 3–4，或把 `executor_refresh_time` 调到 5。成交太少：确认 maker 费率，或把第 0 档保持 1 tick。库存顶到 65%：`min_skew` 已经会砍积累边，必要时再收 `max_base_pct`。

## 文件

- `pmm_mister_hft.py` — 控制器，复制到 `controllers/generic/`
- `conf_pmm_mister_hft_btc_paper.yml` — 纸交易
- `conf_pmm_mister_hft_btc.yml` — 现货小资金
- `conf_client_tick_size.yml.snippet` — 时钟
