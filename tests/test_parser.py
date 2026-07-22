import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scraper.parser import parse_daily_page, _extract_sections, _is_data_line


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "quotations_sample.htm")


def read_fixture():
    with open(FIXTURE_PATH, "r", encoding="iso-8859-1") as f:
        return f.read()


def test_market_highlights_parsing():
    html = read_fixture()
    highlights, _, _ = parse_daily_page(html, date(2026, 7, 21))

    assert highlights is not None
    assert highlights.securities_traded == 8315
    assert highlights.advanced == 5348
    assert highlights.declined == 4559
    assert highlights.unchanged == 5777
    assert highlights.turnover_hkd is not None
    assert highlights.turnover_hkd > 0
    assert highlights.turnover_shares is not None


def test_quotations_parsing():
    html = read_fixture()
    _, quotes, _ = parse_daily_page(html, date(2026, 7, 21))

    assert len(quotes) > 0

    ckh = next((q for q in quotes if q.stock_code == "1"), None)
    assert ckh is not None
    assert ckh.stock_name == "CKH HOLDINGS"
    assert ckh.currency == "HKD"
    assert ckh.prev_close is not None
    assert ckh.closing is not None

    hsbc = next((q for q in quotes if q.stock_code == "5"), None)
    assert hsbc is not None
    assert hsbc.stock_name == "HSBC HOLDINGS"
    assert hsbc.closing is not None
    assert hsbc.prev_close is not None

    clp = next((q for q in quotes if q.stock_code == "2"), None)
    assert clp is not None
    assert clp.closing is not None


def test_suspended_stock():
    html = read_fixture()
    _, quotes, _ = parse_daily_page(html, date(2026, 7, 21))

    wisdom = next((q for q in quotes if q.stock_code == "7"), None)
    assert wisdom is not None
    assert wisdom.stock_name == "WISDOM WEALTH"
    assert wisdom.closing is None


def test_star_prefixed_stock():
    html = read_fixture()
    _, quotes, _ = parse_daily_page(html, date(2026, 7, 21))

    for q in quotes:
        assert q.stock_code is not None
        assert len(q.stock_code) > 0
        assert q.stock_name is not None


def test_no_derivative_products():
    html = read_fixture()
    _, quotes, _ = parse_daily_page(html, date(2026, 7, 21))

    for q in quotes:
        assert int(q.stock_code) < 10000


def test_short_selling_parsing():
    html = read_fixture()
    _, _, short = parse_daily_page(html, date(2026, 7, 21))

    assert len(short) > 0

    ckh_ss = next((s for s in short if s.stock_code == "1"), None)
    assert ckh_ss is not None
    assert ckh_ss.short_shares is not None
    assert ckh_ss.short_turnover is not None
    assert ckh_ss.total_shares is not None
    assert ckh_ss.total_turnover is not None


def test_sections_extraction():
    html = read_fixture()
    sections = _extract_sections(html)
    assert "market_highlights" in sections
    assert "quotations" in sections
    assert "short_selling" in sections


def test_all_stocks_have_valid_currency():
    html = read_fixture()
    _, quotes, _ = parse_daily_page(html, date(2026, 7, 21))

    for q in quotes:
        if q.closing is not None:
            assert q.currency in ("HKD", "RMB", "USD", "CNY")
