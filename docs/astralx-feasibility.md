# AstralX 上跑 `pmm_mister_hft` 的可行性

结论先说：**不能把现有 Hummingbot `pmm_mister_hft` 原样接到 AstralX。** AstralX 线上确有 `/openapi/` 合约接口，但完整下单字段要以你的 V9 PDF 为准。先前用 Websea 文档做的「张数 / 10 QPS / 无 WS 深度」**只适用于 Websea，不适用于 ASX**。

拆成三层（A 依赖 PDF；B/C 在没 PDF 时只能说 Hummingbot 接不上、1.5 bps 仍要先看 ASX 盘口和费率）：

| 层 | 问题 | 判断 |
| --- | --- | --- |
| A 下单 | 能否按 20x、约 800 USDT 名义开平 BTC 永续 | **待 V9 PDF / 鉴权探测**；CCXT 草稿有 `/openapi/contract/order` |
| B 基础设施 | 能否在 Hummingbot 里贴盘口、只挂 maker、秒级撤改 | **现在不行**（无官方 connector） |
| C 参数经济 | 1.5 bps 止盈、5 bps 止损是否赚得到 | **未知**（不要用 Websea 盘口代替） |

本机路径 `D:\Users\jiawe\Desktop\AstralX\API文档\OpenApi接口文档-V9.pdf` 在这个云环境读不到。下文分两块：AstralX 自己线上探到的接口，以及曾误用作对照的 Websea 公开文档。Websea 的盘口、张数、限频 **不能**当成 AstralX 的规格。

---

## 0. 为什么分析里会出现 Websea？它们是不是同一套？

**不是同一家、也不是同一套线上接口。** 更不是「AstralX 照抄了 Websea」的证据。上次把 Websea 写进来，是代理文档，判断过宽。

出现 Websea 的原因只有这些：

1. 你的 V9 PDF 在云环境读不到，网上几乎搜不到 AstralX 的完整 OpenAPI 页面。
2. CCXT 有一个未合入的 PR，标题写成 [Astralx & websea](https://github.com/ccxt/ccxt/pull/26985)。那是**同一个作者在一个 PR 里交了两个 connector**，不是官方声明两所交易所共用后端。点开代码是两个独立 class。
3. Websea 把文档公开挂在 [webseaex.github.io](https://webseaex.github.io/)，接口也叫 OpenAPI。你的文件名同样是「OpenApi接口文档」，英文 OpenAPI 是通用叫法，不能用来认亲。

线上探测（2026-09-12）对照：

| | AstralX | Websea |
| --- | --- | --- |
| 网站 | `www.astralx.com`（Next.js） | `www.websea.com`（Nuxt） |
| 实际 API 主机 | `https://www.astralx.com/openapi/...` | `https://oapi.websea.com/v1/...` |
| 时间接口 | `GET /openapi/time` → `{"serverTime":...}` | 无此路径形态 |
| 行情 | `GET /openapi/quote/ticker` → `{PEPE_USDT:{lastPrice,...}, ...}` | `{errno, errmsg, result:[...]}` |
| 合约/交易对 | `/openapi/symbol` 等返回 `{code:20401,"Authentication failed"}`（要登录） | `/v1/futures/symbols` 公开返回张数、精度 |
| 鉴权（CCXT 草稿） | HMAC-SHA256，query 带 `timestamp`/`signature`，头 `APIKEY-HEADER` | Header `Token` + `Nonce` + SHA1 `Signature` |
| Websea 路径搬到 ASX | `/v1/futures/depth` 变成官网 HTML；`/openApi/market/symbols` **404** | 正常 JSON |

因此：两家都是中小 CEX，都可能买过白标撮合系统，但**当前暴露出来的 REST 形态对不上**。没有公开材料证明同一公司、同一代码仓，或一家抄另一家。行业里更常见的是：多家交易所分别向不同（或偶尔相同）的 SaaS 厂商买引擎，文档都叫 OpenAPI。

AstralX 自己的合约接口多数要鉴权才能看深度/标记价；没有 V9 PDF 之前，**不要用 Websea 的 10 张、10 QPS、无 WS 深度去给 ASX 下结论**。下面第 2 节起标了「Websea 对照」，只作形态参考。

---

## 1. 文档与主机

| 来源 | 状态 |
| --- | --- |
| 用户本机 V9 PDF | 云环境无法访问 Windows 路径 |
| AstralX 线上 | `https://www.astralx.com/openapi/time`、`/openapi/quote/ticker` 可用；合约类多 20401 |
| `oapi.astralx.com` / `api.astralx.com` / `docs.astralx.com` | 本环境 HTTP 403（WAF） |
| Websea 公开文档 | [webseaex.github.io](https://webseaex.github.io/) — **另一套接口**，仅对照 |
| Hummingbot | **没有** `astralx` connector |
| CCXT | 未合入的 [PR #26985](https://github.com/ccxt/ccxt/pull/26985) 里 `astralx` 与 `websea` 是两个 class |

现有 YAML 写的是 `connector_name: binance_perpetual`。换成 AstralX **不会**因为改一个名字就能跑，必须先写永续 connector（或另写独立下单程序）。

---

## 2. BTC 永续规格（Websea 对照，不是 AstralX 实测）

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

## 3. 策略功能 vs Websea OpenAPI（对照，非 ASX）

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

**已确认**

- AstralX 线上 API 在 `www.astralx.com/openapi/`，与 Websea 的 `/v1` + `{errno,errmsg}` **不是同一套**。
- Hummingbot 没有 AstralX connector，`pmm_mister_hft` 不能改 YAML 就上 ASX。

**仍取决于 V9 PDF**

- 下单字段、张/币数量、post-only、WS 深度、限频、20x、双向持仓。
- 第 2–4 节的 10 张 / 116 tick / 10 QPS 是 **Websea 对照**，不能直接套到 ASX。

**与交易所无关、仍然成立的算术**

- 若 maker 不是接近 0，1.5 bps 毛止盈可能覆盖不了双边手续费（币安普通档已经如此）。

---

## 6. 若仍要在 ASX 做，最小改法

1. 把 V9 PDF 放到仓库或对话附件，核对：真实 REST/WS host、是否有 post-only、是否有 WS depth、20x 与双向持仓、合约费率。
2. 对照 PDF 写 connector：起点是 `https://www.astralx.com/openapi/`（不是 `oapi.websea.com`）。CCXT 草稿走 HMAC-SHA256 + `/openapi/contract/order`。
3. 数量、tick、post-only、WS 深度、限频全部以 PDF 和 ASX 账户实测为准，不要沿用 Websea 的 10 张 / 10 QPS。
4. 在 App 里读真实 maker/taker：若挂单费 ≥ 2 bps/边，1.5 bps 毛止盈仍可能净亏（这条与交易所无关，是费率算术）。
5. 先用最小数量实盘验证限价会不会吃单、20x 是否允许、能否同时挂多空。

相关文件：`strategies/pmm_mister_hft/conf_pmm_mister_hft_btc_astralx.yml.snippet`（对照表，**不能**丢进 Hummingbot 启动）。
