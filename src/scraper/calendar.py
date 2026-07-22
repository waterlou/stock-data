import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

import pytz

from src.config import HKEX_CALENDAR_URL, TZ
from src.scraper.client import fetch_page

logger = logging.getLogger(__name__)


def get_latest_trading_date() -> Optional[date]:
    content = fetch_page(HKEX_CALENDAR_URL)
    if not content:
        return None

    links = re.findall(r'href=[\"\']([^\"\']*dayquot/d(\d{6})e\.htm)[\"\']', content)
    if not links:
        logger.error("No trading day links found on calendar page")
        return None

    dates = []
    for href, code in links:
        try:
            d = datetime.strptime(code, "%y%m%d").date()
            dates.append((d, href))
        except ValueError:
            continue

    if not dates:
        return None

    dates.sort(key=lambda x: x[0], reverse=True)
    return dates[0][0]


def get_previous_trading_date(current: date) -> Optional[date]:
    hkt = pytz.timezone(TZ)
    content = fetch_page(HKEX_CALENDAR_URL)
    if not content:
        return None

    links = re.findall(r'href=[\"\']([^\"\']*dayquot/d(\d{6})e\.htm)[\"\']', content)
    dates = []
    for href, code in links:
        try:
            d = datetime.strptime(code, "%y%m%d").date()
            dates.append(d)
        except ValueError:
            continue

    dates.sort(reverse=True)
    for d in dates:
        if d < current:
            return d
    return None


def format_date_code(d: date) -> str:
    return d.strftime("%y%m%d")
