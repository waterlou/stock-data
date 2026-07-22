import os
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.database.queries import (
    get_stocks, get_stock_by_code, get_quotations, get_adjusted_quotations,
    get_market_highlights, get_short_selling, get_trading_dates,
    get_scrape_logs, get_dashboard_stats, get_corporate_actions_for_stock,
)

app = FastAPI(title="HKEX Stock Data API", version="1.0.0")

static_dir = os.path.join(os.path.dirname(__file__), "static")


def serialize(val):
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, date):
        return val.isoformat()
    return val


def rows_to_json(rows):
    return [dict((k, serialize(v)) for k, v in row.items()) for row in rows]


@app.get("/api/overview")
def overview():
    stats = get_dashboard_stats()
    if stats["latest_trade_date"]:
        stats["latest_trade_date"] = stats["latest_trade_date"].isoformat()
    return stats


@app.get("/api/stocks")
def list_stocks(
    search: str = "",
    status: str = "active",
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    rows, total = get_stocks(search, status, limit, offset)
    return {"stocks": rows_to_json(rows), "total": total}


@app.get("/api/stocks/{stock_code}")
def stock_detail(stock_code: str):
    stock = get_stock_by_code(stock_code)
    if not stock:
        return {"error": "Stock not found"}, 404
    return {k: serialize(v) for k, v in stock.items()}


@app.get("/api/stocks/{stock_code}/quotations")
def stock_quotations(
    stock_code: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None
    rows, total = get_quotations(stock_code, fd, td, limit, offset)
    return {"quotations": rows_to_json(rows), "total": total}


@app.get("/api/stocks/{stock_code}/adjusted")
def stock_adjusted(
    stock_code: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None
    rows, total = get_adjusted_quotations(stock_code, fd, td, limit, offset)
    return {"adjusted": rows_to_json(rows), "total": total}


@app.get("/api/stocks/{stock_code}/corporate-actions")
def stock_corporate_actions(stock_code: str):
    actions = get_corporate_actions_for_stock(stock_code)
    return {
        "actions": [
            {
                "stock_code": a.stock_code,
                "action_date": a.action_date.isoformat(),
                "action_type": a.action_type,
                "split_ratio": a.split_ratio,
                "dividend_amount": a.dividend_amount,
                "source": a.source,
            }
            for a in actions
        ]
    }


@app.get("/api/market-highlights")
def market_highlights(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None
    rows, total = get_market_highlights(fd, td, limit, offset)
    return {"highlights": rows_to_json(rows), "total": total}


@app.get("/api/short-selling")
def short_selling(
    stock_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    td = date.fromisoformat(trade_date) if trade_date else None
    rows, total = get_short_selling(stock_code, td, limit, offset)
    return {"entries": rows_to_json(rows), "total": total}


@app.get("/api/dates")
def trading_dates(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    rows, total = get_trading_dates(limit, offset)
    return {"dates": [d.isoformat() if isinstance(d, date) else d for d in rows], "total": total}


@app.get("/api/scrape-logs")
def scrape_logs(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows, total = get_scrape_logs(limit, offset)
    return {"logs": rows_to_json(rows), "total": total}


if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
