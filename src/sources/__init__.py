from src.sources.registry import (
    register_source, get_source, get_all_sources, enabled_sources_for, best_source,
)
from src.sources.hkex import HkexSource
from src.sources.yahoo import YahooSource

register_source(HkexSource())
register_source(YahooSource())
