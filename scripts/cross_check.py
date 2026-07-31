"""Cross-check price data across data sources.

Usage:
    python -m scripts.cross_check
    python -m scripts.cross_check 0700.HK 09988.HK 600519.SH

Compares close prices for the same ticker/date across all applicable sources
and reports mismatches beyond a tolerance.
"""
import sys
from datetime import date, timedelta

from src.sources import registry
from src.sources.hkex import get_latest_trading_date
from src.sources.tencent import TencentSource
from src.sources.yahoo import YahooSource

TOLERANCE_PCT = 1.0  # max allowed relative difference (%)

# CN tickers need exchange-suffixed symbols for yahoo (.SH->.SS, .SZ->.SZ)
_CN_YAHOO = {".SH": ".SS", ".SZ": ".SZ"}


def _series(source, ticker, dfrom, dto):
    prices = source.fetch_prices(ticker, dfrom, dto)
    return {p.trade_date: p for p in prices}


def compare_sources(ticker, market, dfrom, dto, weeks=104):
    dto = dto or date.today()
    dfrom = dfrom or dto - timedelta(weeks=weeks)
    sources = [s for s in registry.enabled_sources_for(market) if s.supports_history]
    if market == "CN":
        yahoo_ticker = ticker[:-3] + _CN_YAHOO.get(ticker[-3:], ".SS")
        sources.append(YahooSource())
        yahoo_ticker = yahoo_ticker  # ticker passed per-source below
    else:
        yahoo_ticker = ticker
    if not sources:
        print(f"{ticker}: no history sources")
        return

    series = {}
    for s in sources:
        t = yahoo_ticker if isinstance(s, YahooSource) and market == "CN" else ticker
        series[s.source_code] = _series(s, t, dfrom, dto)
    if any(len(rows) == 0 for rows in series.values()):
        print(f"{ticker}: some sources returned no data "
              f"({', '.join(f'{k}:{len(v)}' for k, v in series.items())})")

    pairs = list(series.keys())
    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            a, b = pairs[i], pairs[j]
            common = set(series[a]) & set(series[b])
            if not common:
                print(f"{ticker}: no overlapping dates between {a} and {b}")
                continue
            mismatches = 0
            worst = (0.0, None)
            for d in sorted(common):
                ca = _close(series[a][d], market)
                cb = _close(series[b][d], market)
                if ca is None or cb is None or cb == 0:
                    continue
                diff = abs(ca - cb) / cb * 100
                if diff > worst[0]:
                    worst = (diff, d)
                if diff > TOLERANCE_PCT:
                    mismatches += 1
            total = len(common)
            rate = mismatches / total * 100
            status = "OK" if rate < 2.0 else "FAIL"
            print(f"{ticker} [{status}] {a} vs {b}: {total} common dates, "
                  f"{mismatches} mismatches ({rate:.1f}%), worst {worst[0]:.2f}% @ {worst[1]}")


def _close(price, market):
    # Tencent qfq is RAW for HK (adjust ignored) but ADJUSTED for CN.
    # Yahoo raw close is in `close`, adjusted in `adj_close`.
    # HK: raw-to-raw (close). CN: adjusted-to-adjusted (adj_close).
    if market == "HK":
        return float(price.close) if price.close is not None else None
    v = price.adj_close if price.adj_close is not None else price.close
    return float(v) if v is not None else None


def compare_hkex_vs_series(ticker, source_code="yahoo"):
    """Compare one HKEX daily page (raw closes) against a source's raw closes."""
    trade_date = get_latest_trading_date()
    hkex = registry.get_source("hkex")
    data = hkex.fetch_bulk_daily(trade_date)
    hkex_closes = {p.ticker: p.close for p in data["prices"]}
    if ticker not in hkex_closes:
        print(f"{ticker}: not in HKEX page for {trade_date}")
        return
    src = registry.get_source(source_code)
    prices = src.fetch_prices(ticker, trade_date, trade_date)
    if not prices:
        print(f"{ticker}: no {source_code} data for {trade_date}")
        return
    hk = float(hkex_closes[ticker])
    y = float(prices[0].close)
    diff = abs(hk - y) / y * 100
    status = "OK" if diff <= TOLERANCE_PCT else "FAIL"
    print(f"{ticker} [{status}] HKEX {hk} vs {source_code} {y} @ {trade_date} "
          f"({diff:.2f}% diff)")


if __name__ == "__main__":
    from src.sources.normalizer import normalize_ticker, market_from_ticker
    tickers = sys.argv[1:] or ["0700.HK", "09988.HK", "600519.SH"]
    for t in tickers:
        t = t.strip().upper()
        market = market_from_ticker(t) or ("HK" if t.isdigit() and len(t) < 6 else "US")
        canonical = normalize_ticker(t, market)
        compare_sources(canonical, market, None, None)
        print()
    print("--- HKEX raw vs source raw (latest date) ---")
    compare_hkex_vs_series("0700.HK")
    compare_hkex_vs_series("09988.HK")
