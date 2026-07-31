import logging
from datetime import date, timedelta

from src.database import queries
from src.database.connection import get_cursor
from src.sources import registry
from src.sources.hkex import get_latest_trading_date

logger = logging.getLogger(__name__)

FULL_HISTORY_FROM = date(1999, 1, 1)


def run_hk_batch():
    logger.info("Starting HK batch")
    trade_date = get_latest_trading_date()
    if not trade_date:
        logger.warning("No latest HK trading date found")
        return

    bulk_sources = [s for s in registry.enabled_sources_for("HK") if s.supports_bulk_daily]
    if not bulk_sources:
        logger.warning("No HK bulk source available")
        return

    data = {"prices": [], "short_selling": [], "indices": []}
    source = None
    for candidate in bulk_sources:
        try:
            candidate_data = candidate.fetch_bulk_daily(trade_date)
        except Exception as e:
            logger.error("HK bulk fetch failed (%s): %s", candidate.source_code, e)
            queries.record_source_failure(candidate.source_code, str(e))
            continue
        queries.record_source_success(candidate.source_code)
        # Keep index rows from any source; use the first source that yields prices.
        data["indices"] = candidate_data.get("indices") or data["indices"]
        if candidate_data.get("prices"):
            data["prices"] = candidate_data["prices"]
            data["short_selling"] = candidate_data.get("short_selling", [])
            source = candidate
            break

    if not source or not data["prices"]:
        logger.error("HK batch: no bulk source produced price rows")
        queries.log_scan("HK", "hkex", "batch", "error",
                         error_message="no bulk source produced price rows")
        return

    inserted = _save_bulk("HK", data)
    queries.record_source_success(source.source_code)

    if data["indices"]:
        queries.upsert_indices(data["indices"])

    queries.log_scan("HK", source.source_code, "batch", "success",
                     items_processed=len(data["prices"]), items_inserted=inserted)
    logger.info("HK batch done: %d prices inserted (source=%s)", inserted, source.source_code)


def run_us_batch():
    logger.info("Starting US batch")
    rows, total = queries.get_stocks(market="US", watchlist=True, limit=1000)
    if not rows:
        logger.info("No US watchlist stocks to fetch")
        return
    for stock in rows:
        try:
            # Incremental: fetch only since the last stored date (with overlap
            # buffer for adjustments); full history on first fetch.
            date_from = FULL_HISTORY_FROM
            if stock.get("last_date"):
                date_from = stock["last_date"] - timedelta(days=10)
            run_us_stock(stock, date_from)
        except Exception as e:
            logger.error("US batch failed for %s: %s", stock["ticker"], e)
    offset = 1000
    while offset < total:
        more, _ = queries.get_stocks(market="US", watchlist=True, limit=1000, offset=offset)
        if not more:
            break
        for stock in more:
            try:
                date_from = FULL_HISTORY_FROM
                if stock.get("last_date"):
                    date_from = stock["last_date"] - timedelta(days=10)
                run_us_stock(stock, date_from)
            except Exception as e:
                logger.error("US batch failed for %s: %s", stock["ticker"], e)
        offset += len(more)
    source_code = registry.best_source("US", "supports_history").source_code if registry.best_source("US", "supports_history") else "yahoo"
    queries.log_scan("US", source_code, "batch", "success", items_processed=total)
    logger.info("US batch done: %d stocks", total)


def run_us_stock(stock: dict, date_from: date = FULL_HISTORY_FROM, date_to: date = None):
    date_to = date_to or date.today()
    source = registry.best_source("US", "supports_history")
    if not source:
        logger.warning("No history source for US")
        return
    try:
        prices = source.fetch_prices(stock["ticker"], date_from, date_to)
        queries.record_source_success(source.source_code)
    except Exception as e:
        queries.record_source_failure(source.source_code, str(e))
        raise
    if prices:
        for p in prices:
            p.stock_id = stock["id"]
        inserted = queries.upsert_prices(prices)
        queries.mark_fetched(stock["id"])
        _refresh_stock_dates(stock["id"])
        return inserted
    return 0


def run_source_health_check():
    """Probe each registered source with a small known fetch; update health.

    A probe that raises SourceError OR returns too few rows marks the source
    unhealthy (catches both outages and silent empty responses)."""
    from src.sources.base import SourceError
    probes = {"yahoo": ("US", "AAPL", "supports_history", 1, 5),
              "tencent": ("CN", "600519.SH", "supports_history", 1, 14),
              "akshare": ("CN", "600519.SH", "supports_history", 1, 14),
              "hkex": ("HK", "", "supports_bulk_daily", 100, 0),
              "aastocks": ("HK", "", "supports_bulk_daily", 1, 0)}
    probe_date = date.today()
    try:
        probe_date = get_latest_trading_date() or probe_date  # HKEX page lags realtime
    except Exception:
        pass
    for code, (market, ticker, cap, min_rows, window) in probes.items():
        source = registry.get_source(code)
        if not source:
            continue
        try:
            if cap == "supports_bulk_daily":
                result = source.fetch_bulk_daily(probe_date)
                n = len(result.get("indices", []))
            else:
                n = len(source.fetch_prices(ticker, probe_date - timedelta(days=window), probe_date))
            if n < min_rows:
                raise SourceError(f"probe returned only {n} rows (expected >= {min_rows})")
            queries.record_source_success(code)
            logger.info("Health check %s: OK (%d rows)", code, n)
        except Exception as e:
            queries.record_source_failure(code, str(e))
            logger.warning("Health check %s: FAIL (%s)", code, e)


def _save_bulk(market: str, data: dict) -> int:
    inserted = 0
    for price in data["prices"]:
        price.stock_id = queries.upsert_stock(market, price.ticker)
    inserted += queries.upsert_prices(data["prices"])
    for entry in data["short_selling"]:
        entry.stock_id = queries.upsert_stock(market, entry.ticker)
    inserted += queries.upsert_short_selling(data["short_selling"])
    queries.upsert_indices(data.get("indices", []))
    for stock_id in {p.stock_id for p in data["prices"]}:
        queries.mark_fetched(stock_id)
        _refresh_stock_dates(stock_id)
    return inserted


def _refresh_stock_dates(stock_id: int):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE stocks SET first_date = sub.min_d, last_date = sub.max_d, updated_at = NOW()
            FROM (SELECT MIN(trade_date) AS min_d, MAX(trade_date) AS max_d
                  FROM daily_prices WHERE stock_id = %s) sub
            WHERE stocks.id = %s
        """, (stock_id, stock_id))
