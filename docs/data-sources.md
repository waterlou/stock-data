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

## Reliability & Rate Assessment

Grades are based on live testing of the implemented sources and documented SLAs for
the rest. Rate figures are practical caps observed/tested, not marketing numbers.

### Implemented (live, tested)

| Source | Reliability | Rate | Raw vs Adjusted | Markets |
|--------|-------------|------|-----------------|---------|
| **HKEX** | `B` | Unlimited (public page) | Raw | HK |
| **Yahoo** | `B-` | ~200-500/hr soft cap; 5m intraday = 55d | Raw close + adj_close | HK, US, CN (spotty) |
| **Tencent** | `A-` | No observed limit; 640 bars/call | **Raw for HK** (qfq ignored); **adjusted for CN** | HK, CN |
| **AKShare/Sina** | `B` | No observed limit | **QFQ-adjusted for HK + CN**; raw for US | HK, US, CN |
| **AASTOCKS** | `C` | No observed limit | Real-time snapshots, not EOD | HK + CN indices |

### Not implemented (evaluated)

| Source | Reliability | Rate (free) | Markets |
|--------|-------------|-------------|---------|
| **Tiingo** | `A` | 500 calls/day | HK, US, CN |
| **Twelve Data** | `A` | 800 calls/day (US only) | 70+ exchanges at $79/mo |
| **Futu OpenAPI** | `A-` | 100 stocks/week history; 100 subs RT | HK, US, CN (IP-locked) |
| **Tushare** | `A` | Free w/ points system | CN |
| **EOD Historical Data** | `B+` | 20 calls/day | 70+ exchanges |
| **Polygon.io** | `A` | 5 calls/min (US only) | US |
| **Alpha Vantage** | `C` | 25 calls/day | US + global (weak) |

### Reliability grades explained

**`A` / `A-` — Production-grade**
- **Tencent (`A-`)**: JSON API backing their own stock app. Structured, fast, never
  down in testing. Only flaw: qfq adjustment silently ignored for HK (returns raw).
  CN qfq matches Yahoo adjusted within 1%.
- **Tiingo, Twelve Data, Polygon.io, Tushare (`A`)**: Commercial APIs with SLAs,
  documented limits, professional support. You pay for reliability.
- **Futu (`A-`)**: Direct exchange feed quality. But needs a gateway binary running
  + account. China A-shares require mainland IP.

**`B` — Works but has rough edges**
- **HKEX (`B`)**: Official exchange data — highest authority. But HTML scraping is
  fragile; new page formats could break the parser with no warning. Single daily
  fetch, no rate concern.
- **Yahoo (`B-`)**: Reverse-engineered API. Works most of the time but hits
  "possibly delisted" errors, empty returns, and the 60-day intraday boundary is
  flaky (55 works, 60 fails). Soft rate limit is invisible until hit.
- **AKShare/Sina (`B`)**: Sina backend is stable and accurate (matches all sources
  to the cent). But the East Money backend is blocked from our network, so half of
  AKShare's functions are unusable. Heavy dependency (`pandas`); Sina could change
  or block at any time.
- **EOD Historical Data (`B+`)**: Newer provider, wider coverage, less battle-tested.

**`C` — Fragile or not fit for purpose**
- **AASTOCKS (`C`)**: Internal API requiring a specific User-Agent (empty response
  without it). Only index/real-time data, not daily OHLCV. Fine for indices, useless
  for prices.
- **Alpha Vantage (`C`)**: 25 req/day free makes it unusable. Users report slow
  responses and downtime. No HK coverage even paid.

### Key cross-check findings

1. **Tencent qfq ≠ adjusted for HK** — qfq and hfq are identical back to 2016. The
   adjust param is ignored for HK stocks. Don't trust it as an adjusted HK source.
2. **AKShare HK IS qfq-adjusted** — opposite of Tencent. Comparing AKShare HK vs
   Yahoo raw shows ~89% "mismatch" that is entirely the dividend-adjustment delta
   (worst 2.7% on ex-dates).
3. **All sources agree to the cent on recent raw prices** (0700.HK 471.8 across 4
   sources; 600519.SH 1361.76 across 3; AAPL 333.43 across 2). Cross-source
   validation is proven.
4. **Yahoo soft-fails silently** — returned 0 rows for 9988.HK under rapid-fire
   calls but works on retry. The `possibly delisted` error is a false positive from
   rate-limiting.
5. **CN adjusted prices** diverge ±1-2% between providers only on dividend ex-dates —
   methodology variance (Tencent qfq vs Yahoo adj_close), not bad data.

### Recommended source strategy

| Priority | HK | US | CN |
|----------|----|----|-----|
| 1st | HKEX (bulk) | Yahoo (daily) | Tencent (daily) |
| 2nd | Yahoo (history) | AKShare (backup) | AKShare (backup) |
| 3rd | Tencent (history) | Tiingo ($10/mo) | Tiingo ($10/mo) |
| 4th | AKShare (backup) | — | Yahoo (limited) |
