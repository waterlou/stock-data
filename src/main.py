import logging
import signal
import sys
from datetime import date, datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import SCRAPE_TIME, TZ, YFINANCE_SYNC_INTERVAL_DAYS, HKEX_DAILY_URL_TEMPLATE
from src.scraper.client import fetch_page
from src.scraper.calendar import get_latest_trading_date, format_date_code
from src.scraper.parser import parse_daily_page
from src.database.connection import init_database
from src.database import queries
from src.corporate_actions.yfinance_client import fetch_actions_batch
from src.corporate_actions.adjustment import compute_adjusted_quotes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_scrape():
    logger.info("Starting daily scrape")

    try:
        trading_date = get_latest_trading_date()
    except Exception as e:
        logger.error("Failed to get trading date: %s", e)
        queries.log_scrape(date.today(), "calendar", "error", error_message=str(e))
        return

    if trading_date is None:
        logger.warning("No trading date found")
        return

    logger.info("Latest trading date: %s", trading_date)

    if queries.has_data_for_date(trading_date):
        logger.info("Data for %s already exists, skipping", trading_date)
        return

    date_code = format_date_code(trading_date)
    url = HKEX_DAILY_URL_TEMPLATE.format(date_code=date_code)
    logger.info("Fetching: %s", url)

    try:
        html = fetch_page(url)
    except Exception as e:
        logger.error("Failed to fetch daily page: %s", e)
        queries.log_scrape(trading_date, "fetch", "error", error_message=str(e))
        return

    try:
        highlights, quotes, short = parse_daily_page(html, trading_date)
    except Exception as e:
        logger.error("Failed to parse daily page: %s", e)
        queries.log_scrape(trading_date, "parse", "error", error_message=str(e))
        return

    inserted_quotes = 0
    inserted_short = 0

    try:
        if highlights:
            queries.upsert_market_highlights(highlights)
            logger.info("Market highlights saved")

        if quotes:
            inserted_quotes = queries.upsert_daily_quotations(quotes)
            logger.info("Quotations saved: %d rows", inserted_quotes)

            active_codes = set()
            for q in quotes:
                queries.upsert_stock_master(q.stock_code, q.stock_name, q.trade_date)
                queries.update_stock_name_history(q.stock_code, q.stock_name, q.trade_date)
                active_codes.add(q.stock_code)

            queries.detect_delisted_stocks(trading_date, active_codes)

        if short:
            inserted_short = queries.upsert_short_selling(short)
            logger.info("Short selling saved: %d rows", inserted_short)

    except Exception as e:
        logger.error("Failed to save data: %s", e)
        queries.log_scrape(trading_date, "save", "error", error_message=str(e))
        return

    queries.log_scrape(trading_date, "daily", "success",
                       rows_inserted=inserted_quotes + inserted_short)

    logger.info("Scrape completed: %d quotes, %d short selling entries",
                inserted_quotes, inserted_short)

    try:
        new_codes = queries.get_stock_codes_needing_corporate_actions_sync()
        if new_codes:
            logger.info("Syncing corporate actions for %d stocks", len(new_codes))
            actions = fetch_actions_batch(new_codes)
            if actions:
                synced = queries.upsert_corporate_actions(actions)
                logger.info("Corporate actions synced: %d new entries", synced)

                affected_codes = {a.stock_code for a in actions}
                for code in affected_codes:
                    try:
                        adjusted = compute_adjusted_quotes(code)
                        if adjusted:
                            queries.upsert_adjusted_quotations(adjusted)
                    except Exception as e:
                        logger.error("Failed to compute adjusted for %s: %s", code, e)
    except Exception as e:
        logger.error("Failed to sync corporate actions: %s", e)


def run_scrape_once():
    try:
        run_scrape()
    except Exception as e:
        logger.error("Scrape failed: %s", e, exc_info=True)


def main():
    logger.info("Starting HKEX Data Scraper")
    logger.info("Scrape time: %s HKT", SCRAPE_TIME)

    try:
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        sys.exit(1)

    run_scrape_once()

    hour, minute = SCRAPE_TIME.split(":")
    scheduler = BackgroundScheduler(timezone=pytz.timezone(TZ))
    scheduler.add_job(
        run_scrape_once,
        trigger=CronTrigger(hour=int(hour), minute=int(minute)),
        id="daily_scrape",
        name="Daily HKEX scrape",
    )
    scheduler.start()

    logger.info("Scheduler started, waiting for next run at %s HKT", SCRAPE_TIME)

    def shutdown(signum, frame):
        logger.info("Shutting down")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            signal.pause()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
