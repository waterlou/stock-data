import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

import yfinance as yf

from src.models import CorporateAction, Fundamentals, MarketIndex, Price
from src.sources.base import DataSource

logger = logging.getLogger(__name__)


class YahooSource(DataSource):
    source_code = "yahoo"
    source_name = "Yahoo Finance"
    supported_markets = ["HK", "US"]
    supports_history = True
    supports_corporate_actions = True
    supports_fundamentals = True
    supports_bulk_daily = True

    def fetch_prices(self, ticker: str, date_from: date, date_to: date) -> List[Price]:
        try:
            hist = yf.Ticker(ticker).history(
                start=date_from.isoformat(),
                end=(date_to + timedelta(days=1)).isoformat(),
                auto_adjust=False,
            )
        except Exception as e:
            logger.warning("yfinance history failed for %s: %s", ticker, e)
            return []

        prices = []
        for idx, row in hist.iterrows():
            d = idx.date() if hasattr(idx, "date") else datetime.strptime(str(idx)[:10], "%Y-%m-%d").date()
            prices.append(Price(
                trade_date=d,
                stock_id=0,
                source_code=self.source_code,
                open=_dec(row.get("Open")),
                high=_dec(row.get("High")),
                low=_dec(row.get("Low")),
                close=_dec(row.get("Close")),
                adj_close=_dec(row.get("Adj Close")),
                volume=_int(row.get("Volume")),
            ))
        return prices

    def fetch_corporate_actions(self, ticker: str) -> List[CorporateAction]:
        actions: List[CorporateAction] = []
        try:
            t = yf.Ticker(ticker)
        except Exception as e:
            logger.warning("Failed to create yfinance ticker %s: %s", ticker, e)
            return actions

        try:
            splits = t.splits
            if splits is not None and not splits.empty:
                for dt, ratio in splits.items():
                    if ratio is None:
                        continue
                    actions.append(CorporateAction(
                        stock_id=0,
                        action_date=_to_date(dt),
                        action_type="split",
                        split_ratio=float(ratio),
                        source_code=self.source_code,
                    ))
        except Exception as e:
            logger.debug("No splits for %s: %s", ticker, e)

        try:
            dividends = t.dividends
            if dividends is not None and not dividends.empty:
                for dt, amount in dividends.items():
                    if not amount or float(amount) <= 0:
                        continue
                    actions.append(CorporateAction(
                        stock_id=0,
                        action_date=_to_date(dt),
                        action_type="dividend",
                        dividend_amount=float(amount),
                        source_code=self.source_code,
                    ))
        except Exception as e:
            logger.debug("No dividends for %s: %s", ticker, e)

        actions.sort(key=lambda a: a.action_date)
        return actions

    def fetch_fundamentals(self, ticker: str) -> Optional[Fundamentals]:
        try:
            info = yf.Ticker(ticker).info or {}
        except Exception as e:
            logger.warning("yfinance info failed for %s: %s", ticker, e)
            return None
        if not info:
            return None
        return Fundamentals(
            stock_id=0,
            report_date=date.today(),
            source_code=self.source_code,
            market_cap=_dec(info.get("marketCap")),
            pe_ratio=_dec(info.get("trailingPE")),
            eps=_dec(info.get("trailingEps")),
            dividend_yield=_dec(info.get("dividendYield")),
            sector=info.get("sector"),
            industry=info.get("industry"),
        )

    def fetch_bulk_daily(self, trade_date: date) -> dict:
        indices = []
        for code, name in (("^HSI", "Hang Seng Index"), ("^GSPC", "S&P 500")):
            try:
                hist = yf.Ticker(code).history(
                    start=trade_date.isoformat(),
                    end=(trade_date + timedelta(days=1)).isoformat(),
                )
            except Exception as e:
                logger.warning("Index %s failed: %s", code, e)
                continue
            if hist.empty:
                continue
            row = hist.iloc[-1]
            indices.append(MarketIndex(
                trade_date=trade_date,
                market_code="HK" if code == "^HSI" else "US",
                index_code=code,
                index_name=name,
                open=_dec(row.get("Open")),
                high=_dec(row.get("High")),
                low=_dec(row.get("Low")),
                close=_dec(row.get("Close")),
                source_code=self.source_code,
            ))
        return {"prices": [], "short_selling": [], "indices": indices}


def _dec(v):
    if v is None:
        return None
    try:
        return Decimal(str(float(v)))
    except (ValueError, TypeError):
        return None


def _int(v):
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _to_date(dt) -> date:
    if isinstance(dt, datetime):
        return dt.date()
    if isinstance(dt, date):
        return dt
    return datetime.strptime(str(dt)[:10], "%Y-%m-%d").date()
