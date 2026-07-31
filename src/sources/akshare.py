import logging
from datetime import date
from decimal import Decimal
from typing import List

from src.models import Price
from src.sources.base import DataSource
from src.sources.normalizer import market_from_ticker

logger = logging.getLogger(__name__)

_ak = None


def _akshare():
    global _ak
    if _ak is None:
        import akshare  # heavy import; lazy-load only when used
        _ak = akshare
    return _ak


class AkShareSource(DataSource):
    source_code = "akshare"
    source_name = "AKShare"
    supported_markets = ["HK", "US", "CN"]
    supports_history = True

    def fetch_prices(self, ticker: str, date_from: date, date_to: date) -> List[Price]:
        market = market_from_ticker(ticker) or ("HK" if ticker.endswith(".HK") else "US")
        symbol = _to_akshare(ticker)
        ak = _akshare()
        try:
            if market == "CN":
                df = ak.stock_zh_a_daily(
                    symbol=symbol,
                    start_date=date_from.strftime("%Y%m%d"),
                    end_date=date_to.strftime("%Y%m%d"),
                    adjust="qfq",
                )
            elif market == "HK":
                df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            else:
                df = ak.stock_us_daily(symbol=symbol)
        except Exception as e:
            logger.warning("akshare fetch failed for %s: %s", ticker, e)
            return []
        if df is None or df.empty:
            return []

        prices = []
        for row in df.itertuples(index=False):
            try:
                d = _to_date(row.date)
                if d < date_from or d > date_to:
                    continue
                close = _dec(row.close)
                if close is None:
                    continue
                prices.append(Price(
                    trade_date=d,
                    stock_id=0,
                    source_code=self.source_code,
                    ticker=ticker,
                    open=_dec(row.open),
                    high=_dec(row.high),
                    low=_dec(row.low),
                    close=close,
                    adj_close=close if market in ("HK", "CN") else None,  # qfq for HK/CN
                    volume=_int(row.volume),
                ))
            except Exception:
                continue
        return prices


def _to_akshare(ticker: str) -> str:
    t = ticker.upper().strip()
    if t.endswith(".HK"):
        return t[:-3].lstrip("0").zfill(5)
    if t.endswith(".SH"):
        return f"sh{t[:-3]}"
    if t.endswith(".SZ"):
        return f"sz{t[:-3]}"
    return t


def _to_date(v) -> date:
    s = str(v)[:10]
    return date.fromisoformat(s)


def _dec(v):
    try:
        return Decimal(str(v))
    except (ValueError, TypeError):
        return None


def _int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return None
