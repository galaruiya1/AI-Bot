# AI-Bot

基于 [Hummingbot](https://github.com/hummingbot/hummingbot) 的策略检索与笔记仓库。

当前内容来自 Hummingbot `master` 分支（约 2 万 star，Apache 2.0）。官方推荐新策略走 **Strategy V2**（Script / Controller / Executor）；V1 模板仍可用，但不再作为主维护方向。

## 文档

- [Hummingbot 策略全目录](docs/hummingbot-strategies.md) — V2 Controllers、Scripts、Executors、V1 模板、如何启动
- 官方文档：[Strategies](https://hummingbot.org/strategies/) · [V2 示例](https://hummingbot.org/strategies/v2-strategies/examples/) · [V1](https://hummingbot.org/strategies/v1-strategies/)
- AI 编排：[Condor](https://github.com/hummingbot/condor)（LLM 决策 + Hummingbot API 执行）

## 最短启动路径

```bash
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot
make install
conda activate hummingbot

# 纸交易（无需 API key）
hbot create simple_pmm --name conf_paper_bot.yml \
     --set exchange=binance_paper_trade --set trading_pair=BTC-USDT
hbot start conf_paper_bot.yml
```

实盘示例（官方 README 推荐的 `pmm_mister`）：

```bash
hbot connect binance
hbot create pmm_mister --name conf_my_bot.yml \
     --set connector_name=binance --set trading_pair=BTC-USDT --set total_amount_quote=100
hbot start conf_my_bot.yml
```
