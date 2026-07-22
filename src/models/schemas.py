from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class MarketHighlight:
    trade_date: date
    hsi_close: Optional[Decimal] = None
    hsi_change: Optional[Decimal] = None
    hsi_change_pct: Optional[Decimal] = None
    hscei_close: Optional[Decimal] = None
    hscei_change: Optional[Decimal] = None
    hscei_change_pct: Optional[Decimal] = None
    hscci_close: Optional[Decimal] = None
    hscci_change: Optional[Decimal] = None
    hscci_change_pct: Optional[Decimal] = None
    sphkex_largecap_close: Optional[Decimal] = None
    sphkex_largecap_change: Optional[Decimal] = None
    sphkex_largecap_change_pct: Optional[Decimal] = None
    securities_traded: Optional[int] = None
    advanced: Optional[int] = None
    declined: Optional[int] = None
    unchanged: Optional[int] = None
    turnover_hkd: Optional[Decimal] = None
    turnover_shares: Optional[int] = None
    turnover_deals: Optional[int] = None
    rmb_turnover: Optional[Decimal] = None


@dataclass
class StockQuote:
    stock_code: str
    trade_date: date
    stock_name: str
    currency: str = "HKD"
    prev_close: Optional[Decimal] = None
    closing: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    bid: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    shares_traded: Optional[int] = None
    turnover: Optional[Decimal] = None


@dataclass
class ShortSelling:
    stock_code: str
    trade_date: date
    stock_name: str
    short_shares: Optional[int] = None
    short_turnover: Optional[Decimal] = None
    total_shares: Optional[int] = None
    total_turnover: Optional[Decimal] = None


@dataclass
class CorporateAction:
    stock_code: str
    action_date: date
    action_type: str  # 'split' or 'dividend'
    split_ratio: Optional[float] = None
    dividend_amount: Optional[float] = None
    source: str = "yfinance"


@dataclass
class AdjustedQuote:
    stock_code: str
    trade_date: date
    adj_open: Decimal
    adj_high: Decimal
    adj_low: Decimal
    adj_close: Decimal
    adj_volume: int
    adjustment_factor: float
