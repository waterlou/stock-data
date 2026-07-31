# Data Source Comparison

Evaluation of candidate data source APIs for the stock data service. Current sources
(HKEX, Yahoo, Tencent, AASTOCKS, AKShare) are free and unlimited; the question is
whether paid/other sources fill real gaps. Last evaluated: 2026-07.

## Implemented Sources

| Source | Markets | Daily OHLCV | Intraday | Notes |
|--------|---------|-------------|----------|-------|
| HKEX | HK | ✅ whole market | ❌ | HTML scrape, bulk daily page |
| Yahoo (yfinance) | HK, US | ✅ | ✅ 5m (55d) | Rate-limited |
| Tencent | HK, CN | ✅ K-line qfq | ❌ | qfq ignored for HK (returns raw) |
| AASTOCKS | HK | index snapshots | ❌ | HSI/HSCEI/CN indices; needs UA header |
| AKShare (Sina) | HK, US, CN | ✅ qfq for HK/CN | ❌ | Heavy dep (pandas); US is raw |

## Evaluated But Not Implemented

| Source | Free tier | Verdict |
|--------|-----------|---------|
| **Tushare** | free with registration+points | CN-focused, requires token — deferred |
| **EOD Historical Data** | 20 calls/day | $20/mo unlimited; 70+ exchanges — deferred (needs API key) |
| **Tiingo** | 50 tickers, 500 calls/day | Best $10/mo all-round backup — deferred (needs API key) |
| **Twelve Data** | 800 calls/day, US only | Best real-time WebSocket at $79/mo Pro — deferred (needs API key) |
| **Alpha Vantage** | 25 calls/day | Skip — free tier unusable, no HK |
| **Polygon.io** | 5 calls/min, US only | Skip — US only |
| **Futu OpenAPI** | HK LV1/US LV3 free, 100 stocks/week | Good real-time push; needs OpenD gateway + account — deferred |

## Overview (all evaluated)

| Source | Free tier | Daily OHLCV | Intraday | HK | CN | Real-time |
|--------|-----------|-------------|----------|----|----|-----------|
| HKEX (have) | Unlimited | ✅ whole market | ❌ | ✅ | ❌ | ❌ |
| Yahoo (have) | Unlimited | ✅ | ✅ 5m (55d) | ✅ | limited | delayed |
| Tencent (have) | Unlimited | ✅ K-line qfq | ❌ | ✅ | ✅ | delayed |
| AASTOCKS (have) | Unlimited | index snapshots | ❌ | ✅ | indices | delayed |
| AKShare (have) | Unlimited | ✅ | ❌ | ✅ | ✅ | ❌ |
| **Tushare** | free (token) | ✅ | ✅ | ✅ | ✅ | ❓ |
| **EOD Historical Data** | 20 calls/day | ✅ | ✅ ($20/mo) | ✅ | ✅ | ❌ |
| **Tiingo** | 50 tickers, 500 calls/day | ✅ | ✅ ($10/mo) | ✅ | ✅ | IEX ($) |
| **Twelve Data** | 800 calls/day, US only | ✅ | ✅ ($29/mo) | ✅ ($79/mo) | ❓ | ✅ WS ($) |
| **Alpha Vantage** | 25 calls/day | ✅ | ✅ | ❌ | ❌ | delayed |
| **Polygon.io** | 5 calls/min, US only | ✅ | ✅ | ❌ | ❌ | ✅ ($199/mo) |
| **Futu OpenAPI** | HK LV1/US LV3 free | ✅ (100/wk) | ✅ | ✅ | ⚠️ | ✅ |

## Polygon.io (rebranded Massive)

- Free: US stocks only, 5 calls/min, 2yr history, EOD only. No WebSocket.
- $29/mo: unlimited calls, US, 5yr history, 15-min delayed.
- $199/mo: US real-time, 20yr history, WebSocket, second aggregates, trades, quotes.
- Covers: US stocks, options, indices, forex, crypto. **No HK/CN coverage in any tier.**

**Verdict: skip.** US-only, doesn't fill the HK/CN gap.

## Alpha Vantage

- Free: **25 requests/day total** — roughly 2 stock lookups per day. Not usable.
- $49.99/mo: 75 req/min, no daily limit. US + global equities, forex, crypto, technicals, fundamentals.
- "Global equities" = major international names, not full HKEX board.
- Realtime US data requires separate Alpha X Terminal entitlement.

**Verdict: skip.** Free tier unusable; paid doesn't add HK coverage.

## Twelve Data

- Free: 800 calls/day, US stocks/forex/crypto only. No HK.
- Grow ($29/mo): 20+ markets, intraday, fundamentals, 55 credits/min.
- **Pro ($79/mo): 70+ markets including HKEX (XHKG).** Batch requests, earnings, WebSocket.
- Ultra ($329/mo): 84 markets, mutual funds, ETFs.
- Credits: a `/time_series` call = 1 credit per symbol; income statement = 100 credits/symbol.

**Verdict: best HK coverage + real-time WebSocket**, but $79/mo. Good fit for a future
real-time polling phase.

## Tiingo

- Free: 50 unique tickers/month, ~500 calls/day, 5yr EOD US stocks.
- Starter ($10/mo): 500 symbols, higher rate limits, historical intraday (1m/5m/1h), fundamentals, 30yr history.
- Advanced ($30/mo): unlimited symbols.
- Covers US + HK + CN A-shares; IEX real-time feed available.

**Verdict: cheapest all-round backup** ($10/mo) for HK/US/CN daily + intraday + fundamentals.

## What fills which gap

| Gap | Best fill | Cost |
|-----|-----------|------|
| Backup HK daily (HKEX HTML scraping is brittle) | Tiingo / Twelve Data Pro | $10 / $79 |
| Backup intraday (Yahoo rate-limits) | Tiingo | $10 |
| Cross-check Yahoo fundamentals | Tiingo / Alpha Vantage | $10 / $50 |
| Real-time streaming for future polling | Twelve Data Pro | $79 |
| CN A-share backup (Tencent is only source) | Tiingo | $10 |

## Recommendation

- **Now: Tiingo Starter ($10/mo)** — covers all three markets for daily + intraday
  backup at minimal cost.
- **Future real-time phase: Twelve Data Pro ($79/mo)** — XHKG coverage + WebSocket
  streaming when we add live polling.
- **Skip:** Alpha Vantage (free tier unusable, no HK), Polygon.io (US only).
