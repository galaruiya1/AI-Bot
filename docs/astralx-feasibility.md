# AstralX 上跑 `pmm_mister_hft` 的可行性

结论先说：**交易所 API 能做 BTC 永续的开、平、限价、市价和预设止盈止损，但不能把现有 Hummingbot `pmm_mister_hft` 原样接到 AstralX 上当高频策略跑。**

拆成三层：

| 层 | 问题 | 判断 |
| --- | --- | --- |
| A 下单 | 能否按 20x、约 800 USDT 名义开平 BTC 永续 | **能**（数量要改成整数张） |
| B 基础设施 | 能否支撑贴盘口、只挂 maker、秒级撤改 | **弱 / 不够** |
| C 参数经济 | 1.5 bps 止盈、5 bps 止损是否赚得到 | **不匹配**（和在币安上一样，ASX 上更差） |

本机路径 `D:\Users\jiawe\Desktop\AstralX\API文档\OpenApi接口文档-V9.pdf` 在这个云环境读不到。下面依据公开的 [Websea OpenAPI](https://webseaex.github.io/)（CCXT 把 AstralX 与 Websea 视为同一套 OpenAPI），并在 `2026-09-12` 探测了 `https://oapi.websea.com` 的 BTC-USDT 永续盘口。若 V9 PDF 里的主机、字段或权限与此不同，以 PDF 为准，并把差异标回本文。

---

## 1. 文档与主机

| 来源 | 状态 |
| --- | --- |
| 用户本机 V9 PDF | 云环境无法访问 Windows 路径 |
| 公开文档 | [webseaex.github.io](https://webseaex.github.io/) REST + WS |
| 鉴权 | Header：`Token` / `Nonce`（`unix_随机串`，60s 内一次性）/ `Signature`（SHA1） |
| 探测到的公开行情 | `oapi.websea.com` 返回 BTC 永续盘口 |
| `oapi.astralx.com` / `api.astralx.com` / `openapi.astralx.com` | 本环境 HTTP 403（WAF） |
| Hummingbot | **没有** `astralx` / `websea` connector |
| CCXT | `websea` 已有实现；`astralx` 独立 PR 仍未合入（[ccxt#26985](https://github.com/ccxt/ccxt/pull/26985)） |

现有 YAML 写的是 `connector_name: binance_perpetual`。换成 AstralX **不会**因为改一个名字就能跑，必须先写永续 connector（或另写独立下单程序）。

---

## 2. BTC 永续规格（公开 API 实测）

`GET /v1/futures/symbols` 与 `GET /v1/futures/symbol_precision`：

| 字段 | 值 | 对策略的含义 |
| --- | --- | --- |
| `symbol` | `BTC-USDT` | 与现配置交易对一致 |
| `contract_size` / `contract_price` | **0.001 BTC / 张** | 下单单位是张，不是 USDT |
| `min_size` / `minQuantity` | **1 张** | 不能下 0.x 张 |
| `price` 精度 | `"1"`（一位小数） | 与盘口一致，tick = **0.1 USDT** |
| `maker_fee` / `taker_fee` | 接口返回 **`1`** | 不可用，按损坏字段处理 |
| 杠杆 | V1 `lever_rate`（文档示例 10）；V2 `leverage`（文档示例 50） | 官网宣传最高 100x，**20x 大概率允许**，仍需在账户里确认 |
| 保证金 | V1 `is_full`：1 逐仓 / 2 全仓；V2 `margin_mode` | 默认逐仓 |

同一时刻盘口（`GET /v1/futures/depth?symbol=BTC-USDT&limit=5`）：

- 买一 **77323.3** / 卖一 **77323.4**
- 价差 **0.1 USDT ≈ 0.13 bps**
- 卖一附近合计约 2000 张（约 2 BTC），对单笔 10 张足够；持仓量接口互相矛盾（`/v1/futures/24hr` 给出约 12M USDT OI，`/v1/futures/open_interest` 只有约 0.27 BTC），流动性质量不要只看其中一个数字

对应到「每笔 800 USDT」：

| 张数 | 名义（按 mid 77323.35） | 20x 保证金 |
| ---: | ---: | ---: |
| 1 | 77.32 USDT | 3.87 |
| **10** | **773.23 USDT** | **38.66** |
| 11 | 850.56 USDT | 42.53 |

**最接近 800 的是 10 张，不是 800 USDT 这个数字本身。** 双边同时挂 10 张，保证金约 77 USDT，365.81 USDT 账户够用。

---

## 3. 策略功能 vs OpenAPI

`pmm_mister_hft` 实际依赖的能力：

| 策略需要 | OpenAPI 有什么 | 是否够 |
| --- | --- | --- |
| 永续限价开仓 | `POST /v1/futures/order/create`：`contract_type=open`，`type=buy-limit\|sell-limit`，`amount`=张，`lever_rate` | 够 |
| 市价止损 | `buy-market` / `sell-market`；或开仓时带 `stop_loss_price` | 够 |
| 限价止盈 | 开仓带 `stop_profit_price`；或成交后再挂 `close` 限价 | 够，但和 Hummingbot executor 不是同一条路径 |
| `LIMIT_MAKER` / post-only | V1/V2 下单参数 **都没有** `timeInForce`、`post_only`、`LIMIT_MAKER` | **不够**。贴买一/卖一的限价单可能吃掉对手盘，付 taker |
| 双向持仓（HEDGE，买卖同时挂） | V1 是 `open`/`close`；V2 才有 `position_side=long\|short` | **必须先用 V2 验证**能否同时持有多空。若 V1 把反向开仓当成平仓，策略会打穿库存 |
| 盘口定价 `best_bid_ask` | REST `/v1/futures/depth`（最多 100 档）；WS `tickers` 带 bid/ask，**最快 500ms**，且由成交触发 | **不够高频**。文档 **没有 WS 深度频道** |
| 0.1s 时钟刷新、3s 撤改 | 全局限频 **每个 API key 100 次 / 10s（约 10 QPS）**；下单与撤单都算进这个池子 | 买卖各一笔、3s 刷新，REST 轮询深度会很快顶满。文档还写未签名行情可能更严 |
| 批量撤单 | `POST /v1/futures/order/cancel`，`order_ids` 逗号分隔 | 够 |
| 成交回报 | REST 查单 + WS `/ws/v1/futures/order`（订阅本身 10 次 / 10s） | 能做，但不是币安那种密集 user stream |
| 测试网 | 公开文档未给出独立 testnet host | 纸交易不能照搬 `binance_perpetual_testnet` |

V2 下单（更接近双向仓）：

```
POST /v2/futures/order/create
symbol=BTC-USDT
trade_type=open|close
position_side=long|short
order_type=limit|market
margin_mode=isolated|cross
leverage=20
qty=10
qty_type=contract
price=<买一或卖一>
preset_take_profit_price / preset_stop_loss_price
```

V1 的 `stop_profit_price` 与 `stop_loss_price` 各自和 `trigger_price` 互斥，但可以同时带止盈和止损。这比 Hummingbot 成交后再发三重屏障更省限频，**如果**写独立程序，应优先用交易所预设止盈止损，而不是 0.1s 轮询自己补单。

---

## 4. 1.5 bps / 5 bps 在这张盘口上意味着什么

tick = 0.1 USDT，盘口价差约 0.13 bps。

| 目标 | 价格距离 | 约等于 |
| --- | ---: | --- |
| 贴盘（spread = 1 tick） | 0.1 USDT | **0.13 bps** |
| 止盈 1.5 bps | ≈ 11.60 USDT | **116 tick** |
| 止损 5 bps | ≈ 38.66 USDT | **387 tick** |

开仓如果真的只在买一/卖一成交，平仓价要离开盘口一百多个 tick 才到 1.5 bps。BTC 永续这种价差的品种上，这个止盈会挂很久，更容易等到 5 bps 止损或 120s 超时市价离场。

手续费：`/v1/futures/symbols` 的 `maker_fee=1` 不能用。官方「合约交易费率」页在帮助中心，本环境被 Cloudflare 拦住。**没看到真实 maker/taker 之前，不能认为 1.5 bps 毛利能覆盖双边费用。** 若 maker 不是接近 0，净期望与币安分析相同：止盈也可能为负。

资金费率：`/v1/futures/24hr` 当时 `funding_rate=0.000045`（4.5 bps / 期）。短持仓影响小于手续费，但不是零。

---

## 5. 总判断

**可行（有条件）**

- 用 OpenAPI 开/平 BTC-USDT 永续、20x、每笔 10 张（约 773 USDT 名义）。
- 365.81 USDT 覆盖双边保证金后仍有缓冲。
- 交易所原生止盈止损字段能承担三重屏障里的 TP/SL，减少轮询。

**不可行（相对当前策略形态）**

- Hummingbot 里没有 AstralX connector，`pmm_mister_hft` 不能改 YAML 就上 ASX。
- 没有 post-only：`open_order_type: LIMIT_MAKER` 和 `take_profit_order_type: LIMIT_MAKER` 落不到 API 上。
- 没有 WS 深度、ticker 最快 500ms、全局约 10 QPS：做不了策略文档里那种 0.1s 贴盘撤改。
- 1.5 bps 止盈离盘口约 116 tick，和「频繁往返」冲突。
- V1 开平仓语义未必等于币安 HEDGE；未验证前不能同时挂买卖夹单。

因此：AstralX **适合写一个低频、按张数、用交易所止盈止损的开平仓机器人**；**不适合**把现在这份 `pmm_mister_hft` 当高频做市原样上线。

---

## 6. 若仍要在 ASX 做，最小改法

1. 把 V9 PDF 放到仓库或对话附件，核对：真实 REST/WS host、是否有 post-only、是否有 WS depth、20x 与双向持仓、合约费率。
2. 先写 connector 或独立脚本，走 **V2** `position_side` + `qty_type=contract`，数量 **10 张**。
3. 开仓即带 `preset_take_profit_price` / `preset_stop_loss_price`（或 V1 的 `stop_profit_price` / `stop_loss_price`），不要用 0.1s 自建三重屏障刷单。
4. 深度只用 REST，刷新不要短于 1–2s；全局限频按 10 QPS 做节流。
5. 在 App 里读真实 maker/taker：若挂单费 ≥ 2 bps/边，把止盈改到能覆盖双边费之后再谈 1.5 bps 净利。
6. 在账户里用 1 张（约 77 USDT 名义）验证：限价是否会吃单、反向开仓是否变成平仓、20x 是否被拒。

相关文件：`strategies/pmm_mister_hft/conf_pmm_mister_hft_btc_astralx.yml.snippet`（对照表，**不能**丢进 Hummingbot 启动）。
