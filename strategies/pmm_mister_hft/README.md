# pmm_mister_hft — BTC 永续高频夹单

账户按 **365.81 USDT、20x、每笔开仓面值 800 USDT** 来配。一轮完整交易 = 一次开仓 + 一次平仓。

| 项目 | 值 | 金额 |
| --- | --- | --- |
| 保证金 | 365.81 USDT | — |
| 杠杆 | 20x | 理论最大名义 ≈ 7316 USDT |
| 每笔名义 | 800 USDT | 保证金 40 USDT |
| 同时挂单 | 买 1 笔 + 卖 1 笔 | 名义 1600，保证金 80 |
| 止盈 | **1.5 bps** | 0.12 USDT / 轮 |
| 止损 | **5 bps**（市价） | 0.40 USDT / 轮 |
| 超时 | 120s 市价离场 | 防止挂着不动 |

`position_mode` 必须和币安合约账户一致。默认 YAML 是 `HEDGE`；账户若是单向，改成 `ONEWAY`。

## 手续费（必须先看）

1.5 bps 是**毛利**目标。币安 USDT-M 普通档挂单约 **2 bps / 边**，开平各一次 = **4 bps = 0.32 USDT**。

| 结果 | 毛利 | 手续费 | 净利 |
| --- | ---: | ---: | ---: |
| 止盈成交 | +0.12 | −0.32 | **−0.20** |
| 止损成交 | −0.40 | −0.32 | **−0.72** |

在默认费率下，这个 1.5/5 的夹单**期望为负**。要让每轮净赚 1.5 bps，只能：

1. 合约挂单费率接近 0（VIP / 做市返佣），或  
2. 把 `take_profit` 改成 `0.00055`（1.5 bps 净利 + 4 bps 费）

BTC 永续盘口通常只有约 0.1–0.5 bps，1.5 bps 的平仓价离盘口大约 10–15 个 tick（tick=0.1 USDT），成交不会像贴买一那么快。

盈亏比 1.5:5，未计费也要约 **77%** 胜率才打平。

## 安装

```bash
HB=/path/to/hummingbot
cp strategies/pmm_mister_hft/pmm_mister_hft.py $HB/controllers/generic/
cp strategies/pmm_mister_hft/conf_pmm_mister_hft_btc_paper.yml $HB/conf/controllers/
# conf/conf_client.yml → tick_size: 0.1
```

## 先测试网

```bash
conda activate hummingbot
hbot config tick_size 0.1
hbot connect binance_perpetual_testnet
hbot start conf_pmm_mister_hft_btc_paper.yml
hbot status
```

核对：每笔名义约 800、杠杆 20、成交后挂 1.5 bps 止盈、5 bps 打止损。

## 再实盘（小仓已经按 800 名义）

```bash
cp strategies/pmm_mister_hft/conf_pmm_mister_hft_btc.yml $HB/conf/controllers/
hbot connect binance_perpetual
hbot start conf_pmm_mister_hft_btc.yml
```

不要再加杠杆。365.81 USDT 在 20x 下够支付 80 USDT 双边保证金，仍留有爆仓缓冲；不要把 `max_active_executors_by_level` 调大，否则名义会叠上去。

## 热更新

```bash
hbot config take_profit 0.00055   # 想要净 1.5 bps（按 2bps 挂单费）
hbot config stop_loss 0.0005
hbot config order_notional_quote 800
hbot config leverage 20
hbot config manual_kill_switch true
```

## AstralX

不要改 `connector_name` 就接到 AstralX。Hummingbot 没有该交易所 connector；公开 OpenAPI 也没有 post-only / WS 深度，全局限频约 10 QPS。数量若上 ASX，应用 **10 张**（1 张 = 0.001 BTC，约 773 USDT 名义），不是 800 这个数字。详见 [AstralX 可行性](../../docs/astralx-feasibility.md)。

## 文件

- `pmm_mister_hft.py` → `controllers/generic/`
- `conf_pmm_mister_hft_btc_paper.yml` — 测试网
- `conf_pmm_mister_hft_btc.yml` — 实盘 BTCUSDT 永续（币安）
- `conf_pmm_mister_hft_btc_astralx.yml.snippet` — ASX 对照草稿，不能启动
- `conf_client_tick_size.yml.snippet` — 0.1s 时钟
