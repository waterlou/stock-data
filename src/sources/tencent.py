import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

import requests

from src.models import Price
from src.sources.base import DataSource, SourceError

logger = logging.getLogger(__name__)

KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


class TencentSource(DataSource):
    source_code = "tencent"
    source_name = "Tencent Finance"
    supported_markets = ["HK", "CN"]
    supports_history = True

    def fetch_prices(self, ticker: str, date_from: date, date_to: date) -> List[Price]:
        symbol = to_tencent(ticker)
        prices: List[Price] = []
        cursor_end = date_to
        for _ in range(20):  # safety cap on pagination
            param = f"{symbol},day,,{cursor_end.isoformat()},640,qfq"
            rows = self._kline(symbol, param)
            if not rows:
                break
            chunk = self._parse_rows(rows, ticker)
            if not chunk:
                break
            prices.extend(chunk)
            earliest = chunk[0].trade_date
            if earliest <= date_from or len(rows) < 640:
                break
            cursor_end = earliest
        prices.sort(key=lambda p: p.trade_date)
        return [p for p in prices if date_from <= p.trade_date <= date_to]

    def _kline(self, symbol: str, param: str) -> list:
        url = f"{KLINE_URL}?_var=kl&param={param}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise SourceError(f"Tencent kline failed for {symbol}: {e}") from e
        text = resp.text.strip()
        if text.startswith("kl="):
            text = text[len("kl="):]
        try:
            data = json.loads(text)
        except ValueError as e:
            raise SourceError(f"Tencent kline parse error for {symbol}: {e}") from e
        if data.get("code") != 0:
            raise SourceError(f"Tencent kline error for {symbol}: {data.get('msg')}")
        node = data.get("data", {}).get(symbol, {})
        return node.get("qfqday") or node.get("day") or []

    def _parse_rows(self, rows: list, ticker: str) -> List[Price]:
        prices = []
        for row in rows:
            if len(row) < 6:
                continue
            try:
                d = datetime.strptime(row[0], "%Y-%m-%d").date()
                open_p = Decimal(str(row[1]))
                close_p = Decimal(str(row[2]))
                high_p = Decimal(str(row[3]))
                low_p = Decimal(str(row[4]))
                volume = int(float(row[5]))
            except (ValueError, TypeError):
                continue
            prices.append(Price(
                trade_date=d,
                stock_id=0,
                source_code=self.source_code,
                ticker=ticker,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                adj_close=close_p,  # qfq = forward-adjusted
                volume=volume,
            ))
        return prices


def to_tencent(ticker: str) -> str:
    """Canonical ticker -> Tencent symbol. 0700.HK->hk00700, AAPL->usAAPL, 600519.SH->sh600519."""
    t = ticker.upper().strip()
    if t.endswith(".HK"):
        return f"hk{t[:-3].lstrip('0').zfill(5)}"
    if t.endswith(".SH"):
        return f"sh{t[:-3]}"
    if t.endswith(".SZ"):
        return f"sz{t[:-3]}"
    return f"us{t}"
