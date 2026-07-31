import logging
from datetime import date
from decimal import Decimal
from typing import List

import requests

from src.models import MarketIndex
from src.sources.base import DataSource, SourceError

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
INDEX_URL = "https://www.aastocks.com/tc/resources/datafeed/getstockindex.ashx?type=5"

# AASTOCKS index symbol -> (market, our index_code)
_INDEX_MAP = {
    "HSI": ("HK", "^HSI", "Hang Seng Index"),
    "HSCEI": ("HK", "^HSCE", "Hang Seng China Enterprises"),
    "000001.SH": ("CN", "000001.SH", "SSE Composite"),
    "399001.SZ": ("CN", "399001.SZ", "SZSE Component"),
}


class AastocksSource(DataSource):
    source_code = "aastocks"
    source_name = "AASTOCKS"
    supported_markets = ["HK"]
    supports_bulk_daily = True

    def fetch_bulk_daily(self, trade_date: date) -> dict:
        indices = []
        try:
            resp = requests.get(INDEX_URL, headers={"User-Agent": UA}, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            raise SourceError(f"AASTOCKS index fetch failed: {e}") from e

        for item in payload:
            symbol = item.get("symbol", "")
            mapped = _INDEX_MAP.get(symbol)
            if not mapped:
                continue
            market, code, name = mapped
            indices.append(MarketIndex(
                trade_date=trade_date,
                market_code=market,
                index_code=code,
                index_name=name,
                close=_num(item.get("last")),
                change=_num(item.get("change")),  # change field is already signed
                change_pct=_pct(item.get("changeper"), item.get("changesign")),
                source_code=self.source_code,
            ))
        return {"prices": [], "short_selling": [], "indices": indices}


def _num(value):
    if not value:
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _pct(value, sign):
    if not value:
        return None
    try:
        n = Decimal(str(value).replace("%", "").strip())
    except (ValueError, TypeError):
        return None
    return -n if sign == "-" else n
