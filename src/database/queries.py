from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict

from src.database.connection import get_cursor
from src.models.schemas import StockQuote, MarketHighlight, ShortSelling, CorporateAction, AdjustedQuote


def upsert_daily_quotations(quotes: List[StockQuote]) -> int:
    if not quotes:
        return 0
    sql = """
        INSERT INTO daily_quotations (trade_date, stock_code, stock_name, currency,
            prev_close, closing, ask, bid, high, low, shares_traded, turnover)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (trade_date, stock_code) DO NOTHING
    """
    with get_cursor() as cur:
        cur.executemany(sql, [
            (q.trade_date, q.stock_code, q.stock_name, q.currency,
             q.prev_close, q.closing, q.ask, q.bid, q.high, q.low,
             q.shares_traded, q.turnover)
            for q in quotes
        ])
        return cur.rowcount


def upsert_market_highlights(highlight: MarketHighlight) -> bool:
    sql = """
        INSERT INTO market_highlights (trade_date, hsi_close, hsi_change, hsi_change_pct,
            hscei_close, hscei_change, hscei_change_pct,
            hscci_close, hscci_change, hscci_change_pct,
            sphkex_largecap_close, sphkex_largecap_change, sphkex_largecap_change_pct,
            securities_traded, advanced, declined, unchanged,
            turnover_hkd, turnover_shares, turnover_deals, rmb_turnover)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (trade_date) DO NOTHING
    """
    with get_cursor() as cur:
        cur.execute(sql, (
            highlight.trade_date,
            highlight.hsi_close, highlight.hsi_change, highlight.hsi_change_pct,
            highlight.hscei_close, highlight.hscei_change, highlight.hscei_change_pct,
            highlight.hscci_close, highlight.hscci_change, highlight.hscci_change_pct,
            highlight.sphkex_largecap_close, highlight.sphkex_largecap_change, highlight.sphkex_largecap_change_pct,
            highlight.securities_traded, highlight.advanced, highlight.declined, highlight.unchanged,
            highlight.turnover_hkd, highlight.turnover_shares, highlight.turnover_deals, highlight.rmb_turnover,
        ))
        return cur.rowcount > 0


def upsert_short_selling(entries: List[ShortSelling]) -> int:
    if not entries:
        return 0
    sql = """
        INSERT INTO short_selling (trade_date, stock_code, stock_name,
            short_shares, short_turnover, total_shares, total_turnover)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (trade_date, stock_code) DO NOTHING
    """
    with get_cursor() as cur:
        cur.executemany(sql, [
            (s.trade_date, s.stock_code, s.stock_name,
             s.short_shares, s.short_turnover, s.total_shares, s.total_turnover)
            for s in entries
        ])
        return cur.rowcount


def has_data_for_date(trade_date: date) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM market_highlights WHERE trade_date = %s", (trade_date,))
        return cur.fetchone() is not None


def upsert_stock_master(stock_code: str, stock_name: str, trade_date: date):
    sql = """
        INSERT INTO stock_master (stock_code, stock_name, first_trade_date, last_trade_date, status)
        VALUES (%s, %s, %s, %s, 'active')
        ON CONFLICT (stock_code) DO UPDATE SET
            last_trade_date = GREATEST(stock_master.last_trade_date, %s),
            stock_name = %s,
            updated_at = NOW()
    """
    with get_cursor() as cur:
        cur.execute(sql, (stock_code, stock_name, trade_date, trade_date, trade_date, stock_name))


def update_stock_name_history(stock_code: str, stock_name: str, trade_date: date):
    sql = """
        INSERT INTO stock_name_history (stock_code, stock_name, first_seen_date, last_seen_date)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (stock_code, first_seen_date) DO UPDATE SET
            last_seen_date = GREATEST(stock_name_history.last_seen_date, %s)
    """
    with get_cursor() as cur:
        cur.execute(sql, (stock_code, stock_name, trade_date, trade_date, trade_date))


def detect_delisted_stocks(trade_date: date, active_codes: set):
    with get_cursor() as cur:
        cur.execute("""
            SELECT stock_code FROM stock_master
            WHERE status = 'active' AND last_trade_date < %s - INTERVAL '10 days'
        """, (trade_date,))
        inactive = {row[0] for row in cur.fetchall()}
    newly_delisted = inactive - active_codes
    if newly_delisted:
        with get_cursor() as cur:
            cur.execute("""
                UPDATE stock_master SET status = 'delisted', updated_at = NOW()
                WHERE stock_code = ANY(%s)
            """, (list(newly_delisted),))


def upsert_corporate_actions(actions: List[CorporateAction]) -> int:
    if not actions:
        return 0
    sql = """
        INSERT INTO corporate_actions (stock_code, action_date, action_type, split_ratio, dividend_amount, source)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (stock_code, action_date, action_type) DO NOTHING
    """
    with get_cursor() as cur:
        cur.executemany(sql, [
            (a.stock_code, a.action_date, a.action_type, a.split_ratio, a.dividend_amount, a.source)
            for a in actions
        ])
        return cur.rowcount


def get_all_quotations_for_stock(stock_code: str) -> List[Dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT trade_date, closing, high, low,
                   COALESCE(LAG(closing) OVER (ORDER BY trade_date), closing) AS opening,
                   shares_traded
            FROM daily_quotations
            WHERE stock_code = %s
            ORDER BY trade_date
        """, (stock_code,))
        return [dict(row) for row in cur.fetchall()]


def get_corporate_actions_for_stock(stock_code: str) -> List[CorporateAction]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT stock_code, action_date, action_type, split_ratio, dividend_amount, source
            FROM corporate_actions
            WHERE stock_code = %s
            ORDER BY action_date
        """, (stock_code,))
        return [
            CorporateAction(
                stock_code=row["stock_code"],
                action_date=row["action_date"],
                action_type=row["action_type"],
                split_ratio=float(row["split_ratio"]) if row["split_ratio"] else None,
                dividend_amount=float(row["dividend_amount"]) if row["dividend_amount"] else None,
                source=row["source"],
            )
            for row in cur.fetchall()
        ]


def upsert_adjusted_quotations(adjusted: List[AdjustedQuote]) -> int:
    if not adjusted:
        return 0
    sql = """
        INSERT INTO daily_quotations_adjusted (trade_date, stock_code,
            adj_open, adj_high, adj_low, adj_close, adj_volume, adjustment_factor)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (trade_date, stock_code) DO NOTHING
    """
    with get_cursor() as cur:
        cur.executemany(sql, [
            (a.trade_date, a.stock_code, a.adj_open, a.adj_high, a.adj_low,
             a.adj_close, a.adj_volume, a.adjustment_factor)
            for a in adjusted
        ])
        return cur.rowcount


def log_scrape(trade_date: date, section: str, status: str, rows_inserted: int = 0, error_message: str = None):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO scrape_log (trade_date, section, status, rows_inserted, error_message, completed_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (trade_date, section, status, rows_inserted, error_message))


def get_stocks(search: str = "", status: str = "active", limit: int = 100, offset: int = 0) -> tuple:
    sql = """
        SELECT stock_code, stock_name, first_trade_date, last_trade_date, status, updated_at
        FROM stock_master
        WHERE (%s = '' OR stock_code ILIKE %s OR stock_name ILIKE %s)
        AND (%s = '' OR status = %s)
        ORDER BY stock_code
        LIMIT %s OFFSET %s
    """
    search_pattern = f"%{search}%"
    with get_cursor() as cur:
        cur.execute(sql, (search, search_pattern, search_pattern, status, status, limit, offset))
        rows = [dict(row) for row in cur.fetchall()]
        cur.execute("""
            SELECT COUNT(*) FROM stock_master
            WHERE (%s = '' OR stock_code ILIKE %s OR stock_name ILIKE %s)
            AND (%s = '' OR status = %s)
        """, (search, search_pattern, search_pattern, status, status))
        total = cur.fetchone()[0]
    return rows, total


def get_stock_by_code(stock_code: str) -> Optional[Dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT stock_code, stock_name, first_trade_date, last_trade_date, status, updated_at
            FROM stock_master WHERE stock_code = %s
        """, (stock_code,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_quotations(stock_code: str, from_date: Optional[date] = None,
                   to_date: Optional[date] = None, limit: int = 100, offset: int = 0) -> tuple:
    conditions = ["stock_code = %s"]
    params = [stock_code]
    if from_date:
        conditions.append("trade_date >= %s")
        params.append(from_date)
    if to_date:
        conditions.append("trade_date <= %s")
        params.append(to_date)
    where = " AND ".join(conditions)
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT trade_date, stock_code, stock_name, currency, prev_close,
                   closing, ask, bid, high, low, shares_traded, turnover
            FROM daily_quotations
            WHERE {where}
            ORDER BY trade_date DESC
            LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        rows = [dict(row) for row in cur.fetchall()]
        cur.execute(f"""
            SELECT COUNT(*) FROM daily_quotations WHERE {where}
        """, params)
        total = cur.fetchone()[0]
    return rows, total


def get_adjusted_quotations(stock_code: str, from_date: Optional[date] = None,
                            to_date: Optional[date] = None, limit: int = 100, offset: int = 0) -> tuple:
    conditions = ["stock_code = %s"]
    params = [stock_code]
    if from_date:
        conditions.append("trade_date >= %s")
        params.append(from_date)
    if to_date:
        conditions.append("trade_date <= %s")
        params.append(to_date)
    where = " AND ".join(conditions)
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT trade_date, stock_code, adj_open, adj_high, adj_low, adj_close, adj_volume, adjustment_factor
            FROM daily_quotations_adjusted
            WHERE {where}
            ORDER BY trade_date DESC
            LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        rows = [dict(row) for row in cur.fetchall()]
        cur.execute(f"""
            SELECT COUNT(*) FROM daily_quotations_adjusted WHERE {where}
        """, params)
        total = cur.fetchone()[0]
    return rows, total


def get_market_highlights(from_date: Optional[date] = None, to_date: Optional[date] = None,
                          limit: int = 100, offset: int = 0) -> tuple:
    conditions = []
    params = []
    if from_date:
        conditions.append("trade_date >= %s")
        params.append(from_date)
    if to_date:
        conditions.append("trade_date <= %s")
        params.append(to_date)
    where = " AND ".join(conditions) if conditions else "TRUE"
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT * FROM market_highlights
            WHERE {where}
            ORDER BY trade_date DESC
            LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        rows = [dict(row) for row in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM market_highlights WHERE {where}", params)
        total = cur.fetchone()[0]
    return rows, total


def get_short_selling(stock_code: Optional[str] = None, trade_date: Optional[date] = None,
                      limit: int = 100, offset: int = 0) -> tuple:
    conditions = []
    params = []
    if stock_code:
        conditions.append("stock_code = %s")
        params.append(stock_code)
    if trade_date:
        conditions.append("trade_date = %s")
        params.append(trade_date)
    where = " AND ".join(conditions) if conditions else "TRUE"
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT trade_date, stock_code, stock_name, short_shares, short_turnover, total_shares, total_turnover
            FROM short_selling
            WHERE {where}
            ORDER BY trade_date DESC, stock_code
            LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        rows = [dict(row) for row in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM short_selling WHERE {where}", params)
        total = cur.fetchone()[0]
    return rows, total


def get_trading_dates(limit: int = 100, offset: int = 0) -> tuple:
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT trade_date FROM daily_quotations
            ORDER BY trade_date DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        rows = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_quotations")
        total = cur.fetchone()[0]
    return rows, total


def get_scrape_logs(limit: int = 50, offset: int = 0) -> tuple:
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM scrape_log
            ORDER BY started_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        rows = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM scrape_log")
        total = cur.fetchone()[0]
    return rows, total


def get_dashboard_stats() -> Dict:
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM stock_master WHERE status = 'active'")
        active_stocks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM stock_master WHERE status = 'delisted'")
        delisted_stocks = cur.fetchone()[0]
        cur.execute("SELECT MAX(trade_date) FROM daily_quotations")
        latest_date = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_quotations")
        trading_days = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM daily_quotations")
        total_quotations = cur.fetchone()[0]
    return {
        "active_stocks": active_stocks,
        "delisted_stocks": delisted_stocks,
        "latest_trade_date": latest_date,
        "trading_days": trading_days,
        "total_quotations": total_quotations,
    }


def get_stock_codes_needing_corporate_actions_sync():
    with get_cursor() as cur:
        cur.execute("""
            SELECT sm.stock_code FROM stock_master sm
            WHERE sm.status = 'active'
            AND (
                sm.stock_code NOT IN (SELECT DISTINCT stock_code FROM corporate_actions)
                OR sm.updated_at > (SELECT MAX(created_at) FROM corporate_actions WHERE stock_code = sm.stock_code)
                OR (SELECT MAX(created_at) FROM corporate_actions WHERE stock_code = sm.stock_code)
                    < NOW() - INTERVAL '7 days'
            )
        """)
        return [row[0] for row in cur.fetchall()]
