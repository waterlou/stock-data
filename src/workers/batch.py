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
        queries.log_scan("HK", source.source_code, "batch", "error", error_message=str(e))
        return

    inserted = _save_bulk("HK", data)
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
            run_us_stock(stock)
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
    prices = source.fetch_prices(stock["ticker"], date_from, date_to)
    if prices:
        for p in prices:
            p.stock_id = stock["id"]
        inserted = queries.upsert_prices(prices)
        _refresh_stock_dates(stock["id"])
        return inserted
    return 0


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
