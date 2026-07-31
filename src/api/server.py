import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from src.config import SCRAPE_TIME_HK, SCRAPE_TIME_US, TZ, WORKER_POLL_INTERVAL
from src.database import queries
from src.sources.normalizer import normalize_ticker, market_from_ticker
from src.workers import batch, ondemand

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

static_dir = os.path.join(os.path.dirname(__file__), "static")

_scheduler = None
_worker_thread = None


def start_background():
    global _scheduler, _worker_thread
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=pytz.timezone(TZ))
        hh, mm = SCRAPE_TIME_HK.split(":")
        uh, um = SCRAPE_TIME_US.split(":")
        _scheduler.add_job(batch.run_hk_batch, CronTrigger(hour=int(hh), minute=int(mm)),
                           id="hk_batch", name="HK daily batch")
        _scheduler.add_job(batch.run_us_batch, CronTrigger(hour=int(uh), minute=int(um)),
                           id="us_batch", name="US daily batch")
        _scheduler.start()
        logger.info("Scheduler started (HK %s, US %s)", SCRAPE_TIME_HK, SCRAPE_TIME_US)
    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(
            target=ondemand.process_pending,
            kwargs={"poll_interval": WORKER_POLL_INTERVAL},
            daemon=True,
        )
        _worker_thread.start()
        logger.info("Queue worker started")


@asynccontextmanager
async def lifespan(app):
    start_background()
    yield
    if _scheduler:
        _scheduler.shutdown(wait=False)


app = FastAPI(title="Stock Data API", version="2.0.0", lifespan=lifespan)


def serialize(val):
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, date):
        return val.isoformat()
    return val


def rows_to_json(rows):
    return [dict((k, serialize(v)) for k, v in row.items()) for row in rows]


def resolve_market(ticker: str, market: str = "") -> str:
    if market:
        return market
    m = market_from_ticker(ticker)
    if m:
        return m
    return "HK" if ticker.strip().isdigit() else "US"


def resolve_stock(ticker: str, market: str = "") -> Optional[dict]:
    m = resolve_market(ticker, market)
    canonical = normalize_ticker(ticker, m)
    return queries.get_stock_by_ticker(m, canonical)


@app.get("/api/overview")
def overview():
    stats = queries.get_dashboard_stats()
    stats["latest_trade_date"] = serialize(stats["latest_trade_date"])
    return stats


@app.get("/api/markets")
def markets():
    return {"markets": rows_to_json(queries.get_markets())}


@app.get("/api/sources")
def sources():
    return {"sources": rows_to_json(queries.get_sources())}


@app.get("/api/stocks")
def list_stocks(
    search: str = "",
    market: str = "",
    watchlist: bool = None,
    status: str = "",
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    rows, total = queries.get_stocks(search, market, watchlist, status, limit, offset)
    return {"stocks": rows_to_json(rows), "total": total}


@app.get("/api/watchlist")
def watchlist(market: str = ""):
    rows, _ = queries.get_stocks(market=market, watchlist=True, limit=1000)
    return {"stocks": rows_to_json(rows)}


@app.post("/api/watchlist")
def add_to_watchlist(body: dict):
    tickers = body.get("tickers", [])
    market = body.get("market", "")
    added = []
    for t in tickers:
        m = market or market_from_ticker(t) or "HK"
        canonical = normalize_ticker(t, m)
        stock_id = queries.upsert_stock(m, canonical)
        queries.update_stock_watchlist(stock_id, True)
        added.append(canonical)
    return {"added": added}


@app.delete("/api/watchlist/{ticker}")
def remove_from_watchlist(ticker: str, market: str = ""):
    stock = resolve_stock(ticker, market)
    if not stock:
        return {"removed": False}
    queries.update_stock_watchlist(stock["id"], False)
    return {"removed": True, "ticker": stock["ticker"]}


@app.post("/api/watchlist/import")
def import_watchlist(body: dict):
    text = body.get("text", "")
    market = body.get("market", "")
    added = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("ticker"):
            continue
        parts = line.split(",")
        t = parts[0].strip()
        if not t:
            continue
        m = market or market_from_ticker(t) or "HK"
        try:
            canonical = normalize_ticker(t, m)
        except ValueError:
            continue
        stock_id = queries.upsert_stock(m, canonical)
        queries.update_stock_watchlist(stock_id, True)
        added.append(canonical)
    return {"added": added}


@app.get("/api/watchlist/export")
def export_watchlist(market: str = ""):
    rows, _ = queries.get_stocks(market=market, watchlist=True, limit=1000)
    lines = ["ticker,name,market"]
    for r in rows:
        lines.append(f"{r['ticker']},{r['name'] or ''},{r['market_code']}")
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/csv")


@app.get("/api/stocks/{ticker}/prices")
def stock_prices(
    ticker: str,
    market: str = "",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    stock = resolve_stock(ticker, market)
    if not stock:
        m = resolve_market(ticker, market)
        queries.enqueue(m, normalize_ticker(ticker, m), "price")
        return {"status": "queued", "message": "Data is being fetched. Retry in ~30s."}, 202

    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None
    rows, total = queries.get_prices(stock["id"], fd, td, limit, offset)
    if not rows:
        queries.enqueue(stock["market_code"], stock["ticker"], "price")
        return {"status": "queued", "message": "Data is being fetched. Retry in ~30s."}, 202
    return {"prices": rows_to_json(rows), "total": total}


@app.get("/api/stocks/{ticker}/corporate-actions")
def stock_corporate_actions(ticker: str, market: str = ""):
    stock = resolve_stock(ticker, market)
    if not stock:
        m = resolve_market(ticker, market)
        queries.enqueue(m, normalize_ticker(ticker, m), "corporate_actions")
        return {"status": "queued", "message": "Corporate actions are being fetched."}, 202
    actions = queries.get_corporate_actions(stock["id"])
    if not actions:
        queries.enqueue(stock["market_code"], stock["ticker"], "corporate_actions")
        return {"status": "queued", "message": "Corporate actions are being fetched."}, 202
    return {"actions": rows_to_json(actions)}


@app.get("/api/stocks/{ticker}/fundamentals")
def stock_fundamentals(ticker: str, market: str = ""):
    stock = resolve_stock(ticker, market)
    if not stock:
        m = resolve_market(ticker, market)
        queries.enqueue(m, normalize_ticker(ticker, m), "fundamentals")
        return {"status": "queued", "message": "Fundamentals are being fetched."}, 202
    f = queries.get_fundamentals(stock["id"])
    if not f:
        queries.enqueue(stock["market_code"], stock["ticker"], "fundamentals")
        return {"status": "queued", "message": "Fundamentals are being fetched."}, 202
    return {"fundamentals": rows_to_json([f])[0]}


@app.get("/api/indices")
def indices(
    market: str = "",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None
    rows, total = queries.get_indices(market, fd, td, limit, offset)
    return {"indices": rows_to_json(rows), "total": total}


@app.get("/api/short-selling")
def short_selling(
    ticker: str = "",
    market: str = "",
    trade_date: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    stock = None
    if ticker:
        stock = resolve_stock(ticker, market)
        if not stock:
            return {"entries": [], "total": 0}
    td = date.fromisoformat(trade_date) if trade_date else None
    rows, total = queries.get_short_selling(
        stock["id"] if stock else None, td, limit, offset)
    return {"entries": rows_to_json(rows), "total": total}


@app.get("/api/queue")
def queue(limit: int = Query(default=100, le=500)):
    rows, total = queries.get_queue(limit)
    return {"items": rows_to_json(rows), "total": total}


@app.get("/api/logs")
def logs(limit: int = Query(default=50, le=200)):
    rows, total = queries.get_scan_logs(limit)
    return {"logs": rows_to_json(rows), "total": total}


if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
