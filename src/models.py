from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class Stock:
    id: int
    market_code: str
    ticker: str
    name: str = ""
    watchlist: bool = False
    status: str = "active"
    first_date: Optional[date] = None
    last_date: Optional[date] = None


@dataclass
class Price:
    trade_date: date
    stock_id: int
    source_code: str
    ticker: str = ""
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    adj_close: Optional[Decimal] = None
    volume: Optional[int] = None
    prev_close: Optional[Decimal] = None
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    currency: Optional[str] = None


@dataclass
class CorporateAction:
    stock_id: int
    action_date: date
    action_type: str
    split_ratio: Optional[float] = None
    dividend_amount: Optional[float] = None
    source_code: str = "yahoo"


@dataclass
class MarketIndex:
    trade_date: date
    market_code: str
    index_code: str
    index_name: str
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    change: Optional[Decimal] = None
    change_pct: Optional[Decimal] = None
    source_code: str = ""


@dataclass
class Fundamentals:
    stock_id: int
    report_date: date
    source_code: str
    market_cap: Optional[Decimal] = None
    pe_ratio: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    sector: Optional[str] = None
    industry: Optional[str] = None


@dataclass
class ShortSelling:
    trade_date: date
    stock_id: int
    source_code: str
    ticker: str = ""
    short_shares: Optional[int] = None
    short_turnover: Optional[Decimal] = None
    total_shares: Optional[int] = None
    total_turnover: Optional[Decimal] = None
