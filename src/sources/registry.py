import logging
from typing import List, Optional

from src.database.connection import get_cursor
from src.sources.base import DataSource

logger = logging.getLogger(__name__)

_sources: dict = {}


def register_source(source: DataSource):
    _sources[source.source_code] = source


def get_source(source_code: str) -> Optional[DataSource]:
    return _sources.get(source_code)


def get_all_sources() -> List[DataSource]:
    return list(_sources.values())


def enabled_sources_for(market: str) -> List[DataSource]:
    """Enabled sources for a market, ordered by priority."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT ms.source_code
            FROM market_sources ms
            JOIN data_sources ds ON ds.source_code = ms.source_code
            WHERE ms.market_code = %s AND ds.enabled
            ORDER BY ms.priority
        """, (market,))
        codes = [row[0] for row in cur.fetchall()]
    result = [get_source(c) for c in codes]
    return [s for s in result if s is not None]


def best_source(market: str, capability: str) -> Optional[DataSource]:
    """First enabled source for the market that supports the capability."""
    for source in enabled_sources_for(market):
        if getattr(source, capability, False):
            return source
    return None
