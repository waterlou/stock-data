import logging
import time
from datetime import date

from src.database import queries
from src.sources import registry
from src.workers import batch
from src.workers.batch import FULL_HISTORY_FROM

logger = logging.getLogger(__name__)

CAPABILITY_BY_TYPE = {
    "price": "supports_history",
    "corporate_actions": "supports_corporate_actions",
    "fundamentals": "supports_fundamentals",
}


def process_queue_item(item: dict):
    market, ticker, data_type = item["market_code"], item["ticker"], item["data_type"]
    capability = CAPABILITY_BY_TYPE.get(data_type, "supports_history")
    source = registry.best_source(market, capability)
    if not source:
        raise RuntimeError(f"No source for {market}/{ticker} {data_type}")

    stock_id = queries.upsert_stock(market, ticker)

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


def process_pending(poll_interval: int = 5):
    while True:
        item = queries.claim_queue_item("ondemand")
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
