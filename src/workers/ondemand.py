import logging
import time
from datetime import date, timedelta

from src.config import INTRADAY_RETENTION_DAYS
from src.database import queries
from src.sources import registry
from src.sources.base import SourceError
from src.workers import batch
from src.workers.batch import FULL_HISTORY_FROM

logger = logging.getLogger(__name__)

# Yahoo intraday availability limits by interval (days); keep a safety margin
INTRADAY_WINDOW_DAYS = {1: 7, 2: 55, 5: 55, 15: 55, 30: 55, 60: 700}

CAPABILITY_BY_TYPE = {
    "price": "supports_history",
    "corporate_actions": "supports_corporate_actions",
    "fundamentals": "supports_fundamentals",
}


def process_queue_item(item: dict):
    market, ticker, data_type = item["market_code"], item["ticker"], item["data_type"]
    stock_id = queries.upsert_stock(market, ticker)

    if data_type.startswith("intraday_"):
        interval = int(data_type.split("_")[1])
        source = registry.best_source(market, "supports_intraday")
        if not source:
            raise RuntimeError(f"No intraday source for {market}")
        # Fetch window must stay within the retention window, otherwise the
        # insert targets a dropped partition and fails.
        window = min(INTRADAY_WINDOW_DAYS.get(interval, 60), INTRADAY_RETENTION_DAYS)
        start = date.today() - timedelta(days=window)
        queries.ensure_intraday_partitions()
        try:
            bars = source.fetch_intraday(ticker, interval, start, date.today())
            for b in bars:
                b.stock_id = stock_id
            queries.upsert_intraday_bars(bars)
            _ok(source.source_code, stock_id)
        except Exception as e:
            _fail(source.source_code, e)
            raise
        return

    capability = CAPABILITY_BY_TYPE.get(data_type, "supports_history")
    source = registry.best_source(market, capability)
    if not source:
        raise RuntimeError(f"No source for {market}/{ticker} {data_type}")

    try:
        if data_type == "price":
            source = registry.best_source(market, "supports_history")
            if not source:
                raise RuntimeError(f"No history source for {market}")
            prices = source.fetch_prices(ticker, FULL_HISTORY_FROM, date.today())
            for p in prices:
                p.stock_id = stock_id
            queries.upsert_prices(prices)
            batch._refresh_stock_dates(stock_id)
        elif data_type == "corporate_actions":
            actions = source.fetch_corporate_actions(ticker)
            for a in actions:
                a.stock_id = stock_id
            queries.upsert_corporate_actions(actions)
        elif data_type == "fundamentals":
            f = source.fetch_fundamentals(ticker)
            if f:
                f.stock_id = stock_id
                queries.upsert_fundamentals(f)
        _ok(source.source_code, stock_id)
    except Exception as e:
        _fail(source.source_code, e)
        raise


def _ok(source_code: str, stock_id: int):
    queries.record_source_success(source_code)
    queries.mark_fetched(stock_id)


def _fail(source_code: str, error: Exception):
    # Only transport-level failures indicate a source outage; per-ticker errors
    # (bad symbol, no data) must not poison the source's health.
    if isinstance(error, SourceError):
        queries.record_source_failure(source_code, str(error))


def process_pending(poll_interval: int = 5):
    while True:
        queries.recover_stale_queue_items()
        item = queries.claim_queue_item()
        if not item:
            time.sleep(poll_interval)
            continue
        try:
            logger.info("Processing queue item: %s", item)
            process_queue_item(item)
            queries.complete_queue_item(item["id"])
        except Exception as e:
            logger.error("Queue item %s failed: %s", item["id"], e)
            queries.complete_queue_item(item["id"], error=str(e))
