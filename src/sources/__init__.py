from src.sources.registry import (
    register_source, get_source, get_all_sources, enabled_sources_for, best_source,
)
from src.sources.hkex import HkexSource
from src.sources.yahoo import YahooSource
from src.sources.tencent import TencentSource
from src.sources.aastocks import AastocksSource
from src.sources.akshare import AkShareSource

register_source(HkexSource())
register_source(YahooSource())
register_source(TencentSource())
register_source(AastocksSource())
register_source(AkShareSource())
