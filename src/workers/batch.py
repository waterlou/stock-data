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

    with_registered = registry.enabled_sources_for("HK")
    source = next((s for s in with_registered if s.supports_bulk_daily), None)
    if not source:
        logger.warning("No HK bulk source available")
        return

    try:
        data = source.fetch_bulk_daily(trade_date)
    except Exception as e:
        logger.error("HK bulk fetch failed: %s", e)
        queries.record_source_failure(source.source_code, str(e))
        queries.log_scan("HK", source.source_code, "batch", "error", error_message=str(e))
        return

    empty = not data.get("prices") and not data.get("short_selling") and not data.get("indices")
    if empty:
        logger.error("HK bulk parsed zero rows (page drift or holiday?)")
        queries.record_source_failure(source.source_code, "bulk fetch returned no rows")
        queries.log_scan("HK", source.source_code, "batch", "error",
                         error_message="bulk fetch returned no rows")
        return

    inserted = _save_bulk("HK", data)
    queries.record_source_success(source.source_code)

    # HKEX page has no index data; fill indices from another bulk source if available.
    for extra in registry.enabled_sources_for("HK"):
        if extra.source_code == source.source_code or not extra.supports_bulk_daily:
            continue
        try:
            extra_data = extra.fetch_bulk_daily(trade_date)
            if extra_data.get("indices"):
                queries.upsert_indices(extra_data["indices"])
                logger.info("HK indices from %s: %d", extra.source_code, len(extra_data["indices"]))
                break
        except Exception as e:
            logger.warning("HK index fill from %s failed: %s", extra.source_code, e)

    queries.log_scan("HK", source.source_code, "batch", "success",
                     items_processed=len(data["prices"]), items_inserted=inserted)
    logger.info("HK batch done: %d prices inserted", inserted)


def run_us_batch():
    logger.info("Starting US batch")
    rows, _ = queries.get_stocks(market="US", watchlist=True, limit=1000)
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
    queries.log_scan("US", "yahoo", "batch", "success", items_processed=len(rows))
    logger.info("US batch done: %d stocks", len(rows))


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
    probes = {"yahoo": ("US", "AAPL", "supports_history", 1),
              "tencent": ("CN", "600519.SH", "supports_history", 1),
              "akshare": ("CN", "600519.SH", "supports_history", 1),
              "hkex": ("HK", "", "supports_bulk_daily", 100),
              "aastocks": ("HK", "", "supports_bulk_daily", 1)}
    probe_date = date.today()
    try:
        probe_date = get_latest_trading_date() or probe_date  # HKEX page lags realtime
    except Exception:
        pass
    for code, (market, ticker, cap, min_rows) in probes.items():
        source = registry.get_source(code)
        if not source:
            continue
        try:
            if cap == "supports_bulk_daily":
                result = source.fetch_bulk_daily(probe_date)
                n = len(result.get("indices", []))
            else:
                n = len(source.fetch_prices(ticker, probe_date - timedelta(days=5), probe_date))
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
