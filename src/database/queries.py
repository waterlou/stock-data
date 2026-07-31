from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from src.database.connection import get_cursor
from src.models import CorporateAction, Fundamentals, MarketIndex, Price, ShortSelling


# ---------------------------------------------------------------- stocks

def upsert_stock(market_code: str, ticker: str, name: str = "") -> int:
    """Insert or update a stock; returns its id."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO stocks (market_code, ticker, name, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (market_code, ticker) DO UPDATE SET
                name = COALESCE(NULLIF(%s, ''), stocks.name),
                updated_at = NOW()
            RETURNING id
        """, (market_code, ticker, name, name))
        return cur.fetchone()[0]


def get_stock_by_ticker(market_code: str, ticker: str) -> Optional[Dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, market_code, ticker, name, watchlist, status, first_date, last_date, updated_at
            FROM stocks WHERE market_code = %s AND ticker = %s
        """, (market_code, ticker))
        row = cur.fetchone()
        return dict(row) if row else None


def get_stock_by_id(stock_id: int) -> Optional[Dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, market_code, ticker, name, watchlist, status, first_date, last_date, updated_at
            FROM stocks WHERE id = %s
        """, (stock_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_stocks(search: str = "", market: str = "", watchlist: bool = None,
               status: str = "", limit: int = 100, offset: int = 0) -> Tuple[List[Dict], int]:
    conditions, params = [], []
    if search:
        conditions.append("(ticker ILIKE %s OR name ILIKE %s)")
        params += [f"%{search}%", f"%{search}%"]
    if market:
        conditions.append("market_code = %s")
        params.append(market)
    if watchlist is not None:
        conditions.append("watchlist = %s")
        params.append(watchlist)
    if status:
        conditions.append("status = %s")
        params.append(status)
    where = " AND ".join(conditions) if conditions else "TRUE"
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT id, market_code, ticker, name, watchlist, status, first_date, last_date, updated_at
            FROM stocks WHERE {where}
            ORDER BY ticker LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM stocks WHERE {where}", params)
        total = cur.fetchone()[0]
    return rows, total


def update_stock_watchlist(stock_id: int, watchlist: bool):
    with get_cursor() as cur:
        cur.execute("UPDATE stocks SET watchlist = %s, updated_at = NOW() WHERE id = %s", (watchlist, stock_id))


# ---------------------------------------------------------------- prices

def upsert_prices(prices: List[Price]) -> int:
    if not prices:
        return 0
    sql = """
        INSERT INTO daily_prices (trade_date, stock_id, source_code,
            open, high, low, close, adj_close, volume, prev_close, bid, ask, currency)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (trade_date, stock_id) DO UPDATE SET
            close = COALESCE(EXCLUDED.close, daily_prices.close),
            adj_close = COALESCE(EXCLUDED.adj_close, daily_prices.adj_close),
            source_code = EXCLUDED.source_code
    """
    with get_cursor() as cur:
        cur.executemany(sql, [
            (p.trade_date, p.stock_id, p.source_code, p.open, p.high, p.low,
             p.close, p.adj_close, p.volume, p.prev_close, p.bid, p.ask, p.currency)
            for p in prices
        ])
        return cur.rowcount


def get_prices(stock_id: int, from_date: Optional[date] = None,
               to_date: Optional[date] = None, limit: int = 100, offset: int = 0) -> Tuple[List[Dict], int]:
    conditions, params = ["stock_id = %s"], [stock_id]
    if from_date:
        conditions.append("trade_date >= %s")
        params.append(from_date)
    if to_date:
        conditions.append("trade_date <= %s")
        params.append(to_date)
    where = " AND ".join(conditions)
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT trade_date, stock_id, source_code, open, high, low, close, adj_close,
                   volume, prev_close, bid, ask, currency
            FROM daily_prices WHERE {where}
            ORDER BY trade_date DESC LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM daily_prices WHERE {where}", params)
        total = cur.fetchone()[0]
    return rows, total


def has_prices(stock_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM daily_prices WHERE stock_id = %s LIMIT 1", (stock_id,))
        return cur.fetchone() is not None


# ---------------------------------------------------------------- short selling

def upsert_short_selling(entries: List[ShortSelling]) -> int:
    if not entries:
        return 0
    sql = """
        INSERT INTO short_selling (trade_date, stock_id, source_code,
            short_shares, short_turnover, total_shares, total_turnover)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (trade_date, stock_id) DO NOTHING
    """
    with get_cursor() as cur:
        cur.executemany(sql, [
            (e.trade_date, e.stock_id, e.source_code,
             e.short_shares, e.short_turnover, e.total_shares, e.total_turnover)
            for e in entries
        ])
        return cur.rowcount


def get_short_selling(stock_id: Optional[int] = None, trade_date: Optional[date] = None,
                      limit: int = 100, offset: int = 0) -> Tuple[List[Dict], int]:
    conditions, params = [], []
    if stock_id:
        conditions.append("stock_id = %s")
        params.append(stock_id)
    if trade_date:
        conditions.append("trade_date = %s")
        params.append(trade_date)
    where = " AND ".join(conditions) if conditions else "TRUE"
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT ss.trade_date, ss.stock_id, ss.source_code, ss.short_shares,
                   ss.short_turnover, ss.total_shares, ss.total_turnover, s.ticker, s.name
            FROM short_selling ss JOIN stocks s ON s.id = ss.stock_id
            WHERE {where}
            ORDER BY ss.trade_date DESC LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM short_selling WHERE {where}", params)
        total = cur.fetchone()[0]
    return rows, total


# ---------------------------------------------------------------- indices

def upsert_indices(indices: List[MarketIndex]) -> int:
    if not indices:
        return 0
    sql = """
        INSERT INTO market_indices (trade_date, market_code, index_code, index_name,
            open, high, low, close, change, change_pct, source_code)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (trade_date, market_code, index_code) DO UPDATE SET
            close = COALESCE(EXCLUDED.close, market_indices.close),
            change = COALESCE(EXCLUDED.change, market_indices.change),
            change_pct = COALESCE(EXCLUDED.change_pct, market_indices.change_pct),
            source_code = EXCLUDED.source_code
    """
    with get_cursor() as cur:
        cur.executemany(sql, [
            (i.trade_date, i.market_code, i.index_code, i.index_name,
             i.open, i.high, i.low, i.close, i.change, i.change_pct, i.source_code)
            for i in indices
        ])
        return cur.rowcount


def get_indices(market: str = "", from_date: Optional[date] = None,
                to_date: Optional[date] = None, limit: int = 100, offset: int = 0) -> Tuple[List[Dict], int]:
    conditions, params = [], []
    if market:
        conditions.append("market_code = %s")
        params.append(market)
    if from_date:
        conditions.append("trade_date >= %s")
        params.append(from_date)
    if to_date:
        conditions.append("trade_date <= %s")
        params.append(to_date)
    where = " AND ".join(conditions) if conditions else "TRUE"
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT * FROM market_indices WHERE {where}
            ORDER BY trade_date DESC, index_code LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM market_indices WHERE {where}", params)
        total = cur.fetchone()[0]
    return rows, total


# ---------------------------------------------------------------- corporate actions

def upsert_corporate_actions(actions: List[CorporateAction]) -> int:
    if not actions:
        return 0
    sql = """
        INSERT INTO corporate_actions (stock_id, action_date, action_type, split_ratio, dividend_amount, source_code)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (stock_id, action_date, action_type) DO NOTHING
    """
    with get_cursor() as cur:
        cur.executemany(sql, [
            (a.stock_id, a.action_date, a.action_type, a.split_ratio, a.dividend_amount, a.source_code)
            for a in actions
        ])
        return cur.rowcount


def get_corporate_actions(stock_id: int) -> List[Dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT stock_id, action_date, action_type, split_ratio, dividend_amount, source_code
            FROM corporate_actions WHERE stock_id = %s ORDER BY action_date
        """, (stock_id,))
        return [dict(r) for r in cur.fetchall()]


def has_corporate_actions(stock_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM corporate_actions WHERE stock_id = %s LIMIT 1", (stock_id,))
        return cur.fetchone() is not None


# ---------------------------------------------------------------- fundamentals

def upsert_fundamentals(f: Fundamentals) -> int:
    sql = """
        INSERT INTO fundamentals (stock_id, report_date, source_code, market_cap,
            pe_ratio, eps, dividend_yield, sector, industry)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (stock_id, report_date, source_code) DO UPDATE SET
            market_cap = EXCLUDED.market_cap,
            pe_ratio = EXCLUDED.pe_ratio,
            eps = EXCLUDED.eps,
            dividend_yield = EXCLUDED.dividend_yield,
            sector = EXCLUDED.sector,
            industry = EXCLUDED.industry
    """
    with get_cursor() as cur:
        cur.execute(sql, (f.stock_id, f.report_date, f.source_code, f.market_cap,
                          f.pe_ratio, f.eps, f.dividend_yield, f.sector, f.industry))
        return cur.rowcount


def get_fundamentals(stock_id: int) -> Optional[Dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM fundamentals WHERE stock_id = %s
            ORDER BY report_date DESC LIMIT 1
        """, (stock_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def has_fundamentals(stock_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM fundamentals WHERE stock_id = %s LIMIT 1", (stock_id,))
        return cur.fetchone() is not None


def recently_fetched(market_code: str, ticker: str, data_type: str, hours: float = 24) -> bool:
    """True if a completed fetch for this (market, ticker, type) succeeded within N hours."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT 1 FROM download_queue
            WHERE market_code = %s AND ticker = %s AND data_type = %s
              AND status = 'completed'
              AND completed_at > NOW() - (%s || ' hours')::interval
            LIMIT 1
        """, (market_code, ticker, data_type, hours))
        return cur.fetchone() is not None


# ---------------------------------------------------------------- queue

def enqueue(market_code: str, ticker: str, data_type: str) -> bool:
    """Add to queue. Returns False if already pending/processing."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO download_queue (market_code, ticker, data_type, status)
            VALUES (%s, %s, %s, 'pending')
            ON CONFLICT DO NOTHING
        """, (market_code, ticker, data_type))
        return cur.rowcount > 0


def claim_queue_item(worker_id: str) -> Optional[Dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, market_code, ticker, data_type FROM download_queue
            WHERE status = 'pending'
            ORDER BY id LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        item = cur.fetchone()
        if item:
            cur.execute("""
                UPDATE download_queue SET status = 'processing', started_at = NOW()
                WHERE id = %s
            """, (item["id"],))
            return dict(item)
    return None


def complete_queue_item(item_id: int, error: str = ""):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE download_queue SET status = %s, completed_at = NOW(), error_message = %s
            WHERE id = %s
        """, ("failed" if error else "completed", error, item_id))


def get_queue(limit: int = 100, offset: int = 0) -> Tuple[List[Dict], int]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM download_queue ORDER BY id DESC LIMIT %s OFFSET %s
        """, (limit, offset))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM download_queue")
        total = cur.fetchone()[0]
    return rows, total


# ---------------------------------------------------------------- logs

def log_scan(market_code: str, source_code: str, scan_type: str, status: str,
             items_processed: int = 0, items_inserted: int = 0, error_message: str = None):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO scan_logs (market_code, source_code, scan_type, status,
                items_processed, items_inserted, error_message, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (market_code, source_code, scan_type, status, items_processed, items_inserted, error_message))


def get_scan_logs(limit: int = 50, offset: int = 0) -> Tuple[List[Dict], int]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM scan_logs ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM scan_logs")
        total = cur.fetchone()[0]
    return rows, total


# ---------------------------------------------------------------- intraday

def upsert_intraday_bars(bars) -> int:
    if not bars:
        return 0
    sql = """
        INSERT INTO intraday_prices (date_time, stock_id, source_code, interval_min,
            open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (date_time, stock_id, interval_min) DO UPDATE SET
            close = COALESCE(EXCLUDED.close, intraday_prices.close),
            source_code = EXCLUDED.source_code
    """
    with get_cursor() as cur:
        cur.executemany(sql, [
            (b.date_time, b.stock_id, b.source_code, b.interval_min,
             b.open, b.high, b.low, b.close, b.volume)
            for b in bars
        ])
        return cur.rowcount


def get_intraday_bars(stock_id: int, interval_min: int, from_date: Optional[date] = None,
                      to_date: Optional[date] = None, limit: int = 1000, offset: int = 0) -> Tuple[List[Dict], int]:
    conditions, params = ["stock_id = %s", "interval_min = %s"], [stock_id, interval_min]
    if from_date:
        conditions.append("date_time >= %s")
        params.append(from_date)
    if to_date:
        conditions.append("date_time <= %s")
        params.append(to_date + timedelta(days=1))
    where = " AND ".join(conditions)
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT date_time, stock_id, source_code, interval_min, open, high, low, close, volume
            FROM intraday_prices WHERE {where}
            ORDER BY date_time DESC LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM intraday_prices WHERE {where}", params)
        total = cur.fetchone()[0]
    return rows, total


def has_intraday(stock_id: int, interval_min: int) -> bool:
    with get_cursor() as cur:
        cur.execute("""
            SELECT 1 FROM intraday_prices WHERE stock_id = %s AND interval_min = %s LIMIT 1
        """, (stock_id, interval_min))
        return cur.fetchone() is not None


def cleanup_old_intraday(days: int = 30):
    with get_cursor() as cur:
        cur.execute("DELETE FROM intraday_prices WHERE date_time < NOW() - INTERVAL '%s days'", (days,))
        return cur.rowcount


# ---------------------------------------------------------------- misc

def get_markets() -> List[Dict]:
    with get_cursor() as cur:
        cur.execute("SELECT market_code, market_name, currency, timezone FROM markets")
        return [dict(r) for r in cur.fetchall()]


def get_sources() -> List[Dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT ds.source_code, ds.source_name, ds.enabled, ms.market_code, ms.priority
            FROM data_sources ds
            LEFT JOIN market_sources ms ON ms.source_code = ds.source_code
            ORDER BY ds.source_code, ms.priority
        """)
        return [dict(r) for r in cur.fetchall()]


def get_dashboard_stats() -> Dict:
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM stocks WHERE status = 'active'")
        total_stocks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM stocks WHERE watchlist")
        watchlist = cur.fetchone()[0]
        cur.execute("SELECT MAX(trade_date) FROM daily_prices")
        latest_date = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_prices")
        trading_days = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM daily_prices")
        total_prices = cur.fetchone()[0]
    return {
        "total_stocks": total_stocks,
        "watchlist": watchlist,
        "latest_trade_date": latest_date,
        "trading_days": trading_days,
        "total_prices": total_prices,
    }
