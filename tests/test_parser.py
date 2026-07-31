import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sources.hkex import _extract_sections, _is_data_line, parse_market_highlights, parse_prices, parse_short_selling


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "quotations_sample.htm")


def read_fixture():
    with open(FIXTURE_PATH, "r", encoding="iso-8859-1") as f:
        return f.read()


def sections():
    return _extract_sections(read_fixture())


def test_market_highlights_parsing():
    idx = parse_market_highlights(sections()["market_highlights"], date(2026, 7, 21))
    hsi = next((i for i in idx if i.index_code == "^HSI"), None)
    assert hsi is not None
    assert hsi.close is not None
    assert hsi.change_pct is not None


def test_quotations_parsing():
    quotes = parse_prices(sections()["quotations"], date(2026, 7, 21))

    assert len(quotes) > 0

    ckh = next((q for q in quotes if q.ticker == "0001.HK"), None)
    assert ckh is not None
    assert ckh.close is not None

    hsbc = next((q for q in quotes if q.ticker == "0005.HK"), None)
    assert hsbc is not None
    assert hsbc.close is not None

    clp = next((q for q in quotes if q.ticker == "0002.HK"), None)
    assert clp is not None
    assert clp.close is not None


def test_suspended_stock():
    quotes = parse_prices(sections()["quotations"], date(2026, 7, 21))
    wisdom = next((q for q in quotes if q.ticker == "0007.HK"), None)
    assert wisdom is not None
    assert wisdom.close is None


def test_star_prefixed_stock():
    for q in parse_prices(sections()["quotations"], date(2026, 7, 21)):
        assert q.ticker is not None
        assert q.ticker.endswith(".HK")


def test_no_derivative_products():
    for q in parse_prices(sections()["quotations"], date(2026, 7, 21)):
        code = q.ticker.replace(".HK", "")
        assert int(code) < 10000


def test_short_selling_parsing():
    entries = parse_short_selling(sections()["short_selling"], date(2026, 7, 21))
    assert len(entries) > 0
    ckh = next((e for e in entries if e.ticker == "0001.HK"), None)
    assert ckh is not None
    assert ckh.short_shares is not None
    assert ckh.short_turnover is not None
    assert ckh.total_shares is not None
    assert ckh.total_turnover is not None


def test_sections_extraction():
    sec = sections()
    assert "market_highlights" in sec
    assert "quotations" in sec
    assert "short_selling" in sec


def test_all_stocks_have_valid_currency():
    for q in parse_prices(sections()["quotations"], date(2026, 7, 21)):
        if q.close is not None:
            assert q.currency in ("HKD", "RMB", "USD", "CNY")


def test_ticker_normalization():
    from src.sources.normalizer import normalize_ticker
    assert normalize_ticker("700", "HK") == "0700.HK"
    assert normalize_ticker("00700", "HK") == "0700.HK"
    assert normalize_ticker("700.HK", "HK") == "0700.HK"
    assert normalize_ticker("00700.HK", "HK") == "0700.HK"
    assert normalize_ticker("aapl", "US") == "AAPL"
    assert normalize_ticker("AAPL.US", "US") == "AAPL"


def test_cn_ticker_normalization():
    from src.sources.normalizer import normalize_ticker, market_from_ticker
    assert normalize_ticker("600519") == "600519.SH"
    assert normalize_ticker("600519.SH") == "600519.SH"
    assert normalize_ticker("sh600519") == "600519.SH"
    assert normalize_ticker("000001") == "000001.SZ"
    assert normalize_ticker("sz000001") == "000001.SZ"
    assert market_from_ticker("600519.SH") == "CN"
    assert market_from_ticker("sz000001") == "CN"
    assert market_from_ticker("0700.HK") == "HK"


def test_tencent_symbol_conversion():
    from src.sources.tencent import to_tencent
    assert to_tencent("0700.HK") == "hk00700"
    assert to_tencent("09988.HK") == "hk09988"
    assert to_tencent("600519.SH") == "sh600519"
    assert to_tencent("000001.SZ") == "sz000001"
