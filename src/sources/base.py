from datetime import date
from typing import List, Optional

from src.models import CorporateAction, Fundamentals, MarketIndex, Price


class DataSource:
    source_code: str = ""
    source_name: str = ""
    supported_markets: List[str] = []

    # Capabilities
    supports_history = False       # per-stock OHLCV history on demand
    supports_bulk_daily = False    # whole-market daily snapshot in one fetch
    supports_corporate_actions = False
    supports_fundamentals = False

    def supports(self, market: str) -> bool:
        return market in self.supported_markets

    def fetch_prices(self, ticker: str, date_from: date, date_to: date) -> List[Price]:
        return []

    def fetch_corporate_actions(self, ticker: str) -> List[CorporateAction]:
        return []

    def fetch_fundamentals(self, ticker: str) -> Optional[Fundamentals]:
        return None

    def fetch_bulk_daily(self, trade_date: date) -> dict:
        """Whole-market snapshot. Returns {'prices': [...], 'short_selling': [...], 'indices': [...]}."""
        return {"prices": [], "short_selling": [], "indices": []}
