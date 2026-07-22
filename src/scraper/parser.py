import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from src.models.schemas import StockQuote, MarketHighlight, ShortSelling
from src.config import REGULAR_STOCK_THRESHOLD

logger = logging.getLogger(__name__)


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
    pre_tags = soup.find_all("pre")
    combined_html = "\n".join(str(pre) for pre in pre_tags)

    section_anchors = [
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

    positions = {}
    for key, anchor in section_anchors:
        idx = combined_html.find(anchor)
        if idx >= 0:
            positions[key] = idx

    sequence = [k for k, _ in section_anchors if k in positions]

    sections = {}
    for i, key in enumerate(sequence):
        start = positions[key]
        if i + 1 < len(sequence):
            end = positions[sequence[i + 1]]
        else:
            end = len(combined_html)

        chunk = combined_html[start:end]
        chunk_soup = BeautifulSoup(chunk, "html.parser")
        sections[key] = chunk_soup.get_text()

    return sections


def parse_market_highlights(text: str, trade_date: date) -> Optional[MarketHighlight]:
    try:
        data = MarketHighlight(trade_date=trade_date)

        hsi_match = re.search(r'HANG SENG INDEX\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([+\-][\d.]+)\s+([+\-][\d.]+)', text)
        if hsi_match:
            data.hsi_close = _parse_number(hsi_match.group(3))
            data.hsi_change = _parse_number(hsi_match.group(4))
            data.hsi_change_pct = _parse_number(hsi_match.group(5))

        hscei_match = re.search(
            r'HANG SENG CHINA\s*\n?\s*ENTERPRISES INDEX\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([+\-][\d.]+)\s+([+\-][\d.]+)',
            text
        )
        if hscei_match:
            data.hscei_close = _parse_number(hscei_match.group(3))
            data.hscei_change = _parse_number(hscei_match.group(4))
            data.hscei_change_pct = _parse_number(hscei_match.group(5))

        hscci_match = re.search(
            r'HANG SENG CHINA-\s*\n?\s*AFF\.?\s*CORP\.?\s*INDEX\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([+\-][\d.]+)\s+([+\-][\d.]+)',
            text
        )
        if hscci_match:
            data.hscci_close = _parse_number(hscci_match.group(3))
            data.hscci_change = _parse_number(hscci_match.group(4))
            data.hscci_change_pct = _parse_number(hscci_match.group(5))

        sp_match = re.search(
            r'S&P\s*/\s*HKEX\s*\n?\s*LARGECAP\s+INDEX\s+([\d.]+)\s+([\d.]+)\s+([+\-][\d.]+)\s+([+\-][\d.]+)',
            text
        )
        if sp_match:
            data.sphkex_largecap_close = _parse_number(sp_match.group(1))
            data.sphkex_largecap_change = _parse_number(sp_match.group(3))
            data.sphkex_largecap_change_pct = _parse_number(sp_match.group(4))

        sec_match = re.search(r'Sec\.\s*Traded:\s*(\d+)', text)
        if sec_match:
            data.securities_traded = int(sec_match.group(1))

        adv_match = re.search(r'Advanced\s*:\s*(\d+)', text)
        if adv_match:
            data.advanced = int(adv_match.group(1))

        dec_match = re.search(r'Declined\s*:\s*(\d+)', text)
        if dec_match:
            data.declined = int(dec_match.group(1))

        unch_match = re.search(r'Unchanged\s*:\s*(\d+)', text)
        if unch_match:
            data.unchanged = int(unch_match.group(1))

        hkd_match = re.search(r"\(HK\$\):\s*([\d,]+)", text)
        if hkd_match:
            data.turnover_hkd = _parse_number(hkd_match.group(1))

        shares_match = re.search(r"\(Shares\):\s*([\d,]+)", text)
        if shares_match:
            data.turnover_shares = _parse_int(shares_match.group(1))

        deals_match = re.search(r"\(Deals\):\s*([\d,]+)", text)
        if deals_match:
            data.turnover_deals = _parse_int(deals_match.group(1))

        rmb_match = re.search(r"Renminbi Products Turnover\s*\(CNY\):\s*([\d,]+)", text)
        if rmb_match:
            data.rmb_turnover = _parse_number(rmb_match.group(1))

        if data.securities_traded is not None or data.turnover_hkd is not None:
            return data
        return None

    except Exception as e:
        logger.error("Error parsing market highlights: %s", e)
        return None


def parse_quotations(text: str, trade_date: date) -> List[StockQuote]:
    quotes = []

    entries = _extract_stock_entries(text)

    for parts in entries:
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
            quotes.append(StockQuote(
                trade_date=trade_date,
                stock_code=code,
                stock_name=name,
                currency=currency,
            ))
            continue

        closing_val = parts.get("closing", "")
        prev_close_val = parts.get("prev_close", "")

        closing = _parse_number(closing_val)
        prev_close = _parse_number(prev_close_val)

        if closing is None and prev_close is None:
            closing = _parse_number(prev_close_val)
            prev_close = None

        quotes.append(StockQuote(
            trade_date=trade_date,
            stock_code=code,
            stock_name=name,
            currency=currency,
            prev_close=prev_close,
            closing=closing,
            ask=_parse_number(parts.get("ask", "")),
            bid=_parse_number(parts.get("bid", "")),
            high=_parse_number(parts.get("high", "")),
            low=_parse_number(parts.get("low", "")),
            shares_traded=_parse_int(parts.get("shares_traded", "")),
            turnover=_parse_number(parts.get("turnover", "")),
        ))

    return quotes


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

        code, name_start = _extract_code_and_name_start(line)
        if code is None:
            i += 1
            continue

        has_continuation = (i + 1 < len(lines) and _is_continuation_line(lines[i + 1]))

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
    s = line.rstrip("\r")
    return bool(re.match(r'^\s{26,}\d', s))


def _extract_code_and_name_start(line: str) -> Tuple[Optional[str], int]:
    m = re.match(r'^\*?\s*(\d{1,5})\s+', line)
    if not m:
        return None, 0
    code = m.group(1).strip()
    return code, m.end()


def _parse_entry_pair(line1: str, line2: Optional[str]) -> dict:
    l1 = line1.rstrip("\r")

    m = re.match(r'^\*?\s*\d{1,5}\s+', l1)
    if not m:
        return {}
    after_code = l1[m.end():]

    parts = _smart_split(after_code)

    name_parts = []
    currency = ""
    numeric_parts = []

    for part in parts:
        if re.match(r'^(HKD|RMB|USD|CNY)$', part) and not currency:
            currency = part
        elif re.match(r'^[\d,]+\.?\d*$', part) and len(numeric_parts) < 4:
            numeric_parts.append(part)
        elif part == "-" and len(numeric_parts) < 4:
            numeric_parts.append(part)
        elif part == "TRADING" and "SUSPENDED" in l1:
            name_parts.append(part)
            name_parts.append("SUSPENDED")
            break
        else:
            if not numeric_parts and not currency:
                name_parts.append(part)
            elif len(numeric_parts) >= 4:
                continue

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
        l2 = line2.rstrip("\r")
        l2_parts = _smart_split(l2.strip())
        l2_nums = []
        for part in l2_parts:
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


def parse_short_selling(text: str, trade_date: date) -> List[ShortSelling]:
    entries = []
    lines = text.split("\n")

    for line in lines:
        if not _is_data_line(line):
            continue

        s = line.rstrip("\r").strip()

        m = re.match(r'^(\d{1,5})\s+(.+)$', s)
        if not m:
            continue

        code = m.group(1)
        if int(code) >= REGULAR_STOCK_THRESHOLD:
            continue

        rest = m.group(2)

        parts = re.split(r'\s{2,}', rest)
        if len(parts) < 5:
            continue

        name = parts[0].strip()
        numbers = parts[1:5]

        entries.append(ShortSelling(
            trade_date=trade_date,
            stock_code=code,
            stock_name=name,
            short_shares=_parse_int(numbers[0]),
            short_turnover=_parse_number(numbers[1]),
            total_shares=_parse_int(numbers[2]),
            total_turnover=_parse_number(numbers[3]),
        ))

    return entries


def parse_daily_page(html: str, trade_date: date) -> Tuple[Optional[MarketHighlight], List[StockQuote], List[ShortSelling]]:
    sections = _extract_sections(html)

    highlights = None
    quotes = []
    short = []

    if "market_highlights" in sections:
        highlights = parse_market_highlights(sections["market_highlights"], trade_date)

    if "quotations" in sections:
        quotes = parse_quotations(sections["quotations"], trade_date)

    if "short_selling" in sections:
        short = parse_short_selling(sections["short_selling"], trade_date)

    return highlights, quotes, short
