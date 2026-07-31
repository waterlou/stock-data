import logging
import re
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from src.config import HKEX_CALENDAR_URL, HKEX_DAILY_URL_TEMPLATE, REGULAR_STOCK_THRESHOLD
from src.models import MarketIndex, Price, ShortSelling
from src.sources.base import DataSource
from src.sources.normalizer import normalize_ticker

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BACKOFF = 5


class HkexSource(DataSource):
    source_code = "hkex"
    source_name = "HKEX"
    supported_markets = ["HK"]
    supports_bulk_daily = True

    def fetch_bulk_daily(self, trade_date: date) -> dict:
        date_code = format_date_code(trade_date)
        url = HKEX_DAILY_URL_TEMPLATE.format(date_code=date_code)
        logger.info("Fetching HKEX daily page: %s", url)
        html = fetch_page(url)
        if not html:
            return {"prices": [], "short_selling": [], "indices": []}
        sections = _extract_sections(html)

        prices, short = [], []
        if "quotations" in sections:
            prices = parse_prices(sections["quotations"], trade_date)
        if "short_selling" in sections:
            short = parse_short_selling(sections["short_selling"], trade_date)
        return {"prices": prices, "short_selling": short, "indices": []}


def get_latest_trading_date() -> Optional[date]:
    content = fetch_page(HKEX_CALENDAR_URL)
    if not content:
        return None
    links = re.findall(r'href=[\"\']([^\"\']*dayquot/d(\d{6})e\.htm)[\"\']', content)
    dates = []
    for href, code in links:
        try:
            dates.append(datetime.strptime(code, "%y%m%d").date())
        except ValueError:
            continue
    if not dates:
        return None
    return max(dates)


def format_date_code(d: date) -> str:
    return d.strftime("%y%m%d")


# ---------------------------------------------------------------- HTTP

def fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.RequestException as e:
            logger.warning("Attempt %d/%d failed for %s: %s", attempt, MAX_RETRIES, url, e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
            else:
                raise
    return None


# ---------------------------------------------------------------- Parser

def _parse_number(value: str) -> Optional[Decimal]:
    value = value.strip()
    if not value or value in ("-", "---", "N/A", ""):
        return None
    value = value.replace(",", "")
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _parse_int(value: str) -> Optional[int]:
    value = value.strip()
    if not value or value in ("-", "---", "N/A", ""):
        return None
    value = value.replace(",", "")
    try:
        return int(value)
    except ValueError:
        return None


def _extract_sections(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    combined_html = "\n".join(str(pre) for pre in soup.find_all("pre"))

    anchors = [
        ("market_highlights", 'name="market_highlights"'),
        ("quotations", 'name="quotations"'),
        ("sales_all", 'name="sales_all"'),
        ("sales_over", 'name="sales_over"'),
        ("amendments", 'name="amendments"'),
        ("dealings_suspstocks", 'name="dealings_suspstocks"'),
        ("adj_turnover", 'name="adj_turnover"'),
        ("short_selling", 'name="short_selling"'),
        ("adj_short", 'name="adj_short"'),
        ("options_exercised", 'name="options_exercised"'),
        ("efn_highlights", 'name="efn_highlights"'),
        ("overseas_highlights", 'name="overseas_highlights"'),
        ("other_info", 'name="other_info"'),
    ]
    positions = {k: combined_html.find(a) for k, a in anchors if combined_html.find(a) >= 0}
    sequence = [k for k, _ in anchors if k in positions]

    sections = {}
    for i, key in enumerate(sequence):
        start = positions[key]
        end = positions[sequence[i + 1]] if i + 1 < len(sequence) else len(combined_html)
        chunk = combined_html[start:end]
        sections[key] = BeautifulSoup(chunk, "html.parser").get_text()
    return sections


def parse_prices(text: str, trade_date: date) -> List[Price]:
    prices = []
    for parts in _extract_stock_entries(text):
        code = parts.get("code")
        if code is None or int(code) >= REGULAR_STOCK_THRESHOLD:
            continue
        name = parts.get("name", "").strip()
        currency = parts.get("currency") or "HKD"
        if currency not in ("HKD", "RMB", "USD", "CNY"):
            continue

        is_suspended = "TRADING SUSPENDED" in name
        if is_suspended:
            name = name.replace("HKD", "").replace("TRADING SUSPENDED", "").strip()
            closing = prev_close = None
        else:
            closing = _parse_number(parts.get("closing", ""))
            prev_close = _parse_number(parts.get("prev_close", ""))
            if closing is None and prev_close is None:
                closing = _parse_number(parts.get("prev_close", ""))
                prev_close = None

        prices.append(Price(
            trade_date=trade_date,
            stock_id=0,
            source_code=self_source_code(),
            ticker=_hk_ticker(code),
            open=None,
            high=_parse_number(parts.get("high", "")),
            low=_parse_number(parts.get("low", "")),
            close=closing,
            adj_close=None,
            volume=_parse_int(parts.get("shares_traded", "")),
            prev_close=prev_close,
            bid=_parse_number(parts.get("bid", "")),
            ask=_parse_number(parts.get("ask", "")),
            currency=currency,
        ))
    return prices


def parse_short_selling(text: str, trade_date: date) -> List[ShortSelling]:
    entries = []
    for line in text.split("\n"):
        if not _is_data_line(line):
            continue
        s = line.rstrip("\r").strip()
        m = re.match(r'^(\d{1,5})\s+(.+)$', s)
        if not m:
            continue
        code = m.group(1)
        if int(code) >= REGULAR_STOCK_THRESHOLD:
            continue
        parts = re.split(r'\s{2,}', m.group(2))
        if len(parts) < 5:
            continue
        numbers = parts[1:5]
        entries.append(ShortSelling(
            trade_date=trade_date,
            stock_id=0,
            source_code=self_source_code(),
            ticker=_hk_ticker(code),
            short_shares=_parse_int(numbers[0]),
            short_turnover=_parse_number(numbers[1]),
            total_shares=_parse_int(numbers[2]),
            total_turnover=_parse_number(numbers[3]),
        ))
    return entries


def parse_market_highlights(text: str, trade_date: date) -> List[MarketIndex]:
    indices = []

    def add(code, name, pattern, close_grp, chg_grp, pct_grp):
        m = re.search(pattern, text)
        if m:
            indices.append(MarketIndex(
                trade_date=trade_date,
                market_code="HK",
                index_code=code,
                index_name=name,
                close=_parse_number(m.group(close_grp)),
                change=_parse_number(m.group(chg_grp)),
                change_pct=_parse_number(m.group(pct_grp)),
                source_code=self_source_code(),
            ))

    add("^HSI", "Hang Seng Index",
        r'HANG SENG INDEX\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([+\-][\d.]+)\s+([+\-][\d.]+)',
        3, 4, 5)
    add("^HSCE", "Hang Seng China Enterprises",
        r'HANG SENG CHINA\s*\n?\s*ENTERPRISES INDEX\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([+\-][\d.]+)\s+([+\-][\d.]+)',
        3, 4, 5)
    add("^HSCCI", "Hang Seng China-Aff Corp",
        r'HANG SENG CHINA-\s*\n?\s*AFF\.?\s*CORP\.?\s*INDEX\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([+\-][\d.]+)\s+([+\-][\d.]+)',
        3, 4, 5)
    add("^SPHKEX", "S&P/HKEX LargeCap",
        r'S&P\s*/\s*HKEX\s*\n?\s*LARGECAP\s+INDEX\s+([\d.]+)\s+([\d.]+)\s+([+\-][\d.]+)\s+([+\-][\d.]+)',
        1, 3, 4)
    return indices


# ---------------------------------------------------------------- helpers

def self_source_code():
    return "hkex"


def _hk_ticker(code: str) -> str:
    return normalize_ticker(code, "HK")


def _extract_stock_entries(text: str) -> List[dict]:
    lines = text.split("\n")
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "CODE  NAME OF STOCK" in line and "PRV.CLO" in line:
            i += 2
            continue
        if not _is_data_line(line):
            i += 1
            continue
        code, _ = _extract_code_and_name_start(line)
        if code is None:
            i += 1
            continue
        has_continuation = i + 1 < len(lines) and _is_continuation_line(lines[i + 1])
        entry = _parse_entry_pair(line, lines[i + 1] if has_continuation else None)
        entry["code"] = code
        entries.append(entry)
        i += 2 if has_continuation else 1
    return entries


def _is_data_line(line: str) -> bool:
    s = line.rstrip("\r")
    if not s:
        return False
    if s.startswith("CODE") or s.startswith("---") or s.startswith("<"):
        return False
    if re.match(r'^\s*[Ss]ec\.?\s*[Tt]raded', s):
        return False
    if re.match(r'^\d{1,2}\s+[A-Z]{3}\s+\d{4}', s):
        return False
    return bool(re.match(r'^\*?\s{0,7}\d{1,5}\s+[A-Z]', s))


def _is_continuation_line(line: str) -> bool:
    return bool(re.match(r'^\s{26,}\d', line.rstrip("\r")))


def _extract_code_and_name_start(line: str) -> Tuple[Optional[str], int]:
    m = re.match(r'^\*?\s*(\d{1,5})\s+', line)
    if not m:
        return None, 0
    return m.group(1).strip(), m.end()


def _parse_entry_pair(line1: str, line2: Optional[str]) -> dict:
    l1 = line1.rstrip("\r")
    m = re.match(r'^\*?\s*\d{1,5}\s+', l1)
    if not m:
        return {}
    parts = _smart_split(l1[m.end():])

    name_parts, currency, numeric_parts = [], "", []
    for part in parts:
        if re.match(r'^(HKD|RMB|USD|CNY)$', part) and not currency:
            currency = part
        elif re.match(r'^[\d,]+\.?\d*$', part) and len(numeric_parts) < 4:
            numeric_parts.append(part)
        elif part == "-" and len(numeric_parts) < 4:
            numeric_parts.append(part)
        elif part == "TRADING" and "SUSPENDED" in l1:
            name_parts += ["TRADING", "SUSPENDED"]
            break
        else:
            if not numeric_parts and not currency:
                name_parts.append(part)

    while len(numeric_parts) < 4:
        numeric_parts.append("")

    entry = {
        "name": " ".join(name_parts),
        "currency": currency,
        "prev_close": numeric_parts[0],
        "ask": numeric_parts[1],
        "high": numeric_parts[2],
        "shares_traded": numeric_parts[3],
        "closing": numeric_parts[0],
        "bid": numeric_parts[1],
        "low": numeric_parts[2],
        "turnover": numeric_parts[3],
    }

    if line2:
        l2_nums = []
        for part in _smart_split(line2.rstrip("\r").strip()):
            if re.match(r'^[\d,]+\.?\d*$', part) and len(l2_nums) < 4:
                l2_nums.append(part)
            elif part == "-" and len(l2_nums) < 4:
                l2_nums.append(part)
            elif len(l2_nums) >= 4:
                break
        while len(l2_nums) < 4:
            l2_nums.append("")
        entry["closing"] = l2_nums[0]
        entry["bid"] = l2_nums[1]
        entry["low"] = l2_nums[2]
        entry["turnover"] = l2_nums[3]
    return entry


def _smart_split(text: str) -> List[str]:
    return re.split(r'\s{2,}', text.strip())
