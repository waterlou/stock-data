import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hkex:hkex@localhost:5432/hkex")
SCRAPE_TIME_HK = os.getenv("SCRAPE_TIME_HK", "17:00")
SCRAPE_TIME_US = os.getenv("SCRAPE_TIME_US", "06:00")
TZ = os.getenv("TZ", "Asia/Hong_Kong")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
WORKER_POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))

HKEX_BASE_URL = "https://www.hkex.com.hk"
HKEX_CALENDAR_URL = f"{HKEX_BASE_URL}/eng/stat/smstat/dayquot/qtn.asp"
HKEX_DAILY_URL_TEMPLATE = f"{HKEX_BASE_URL}/eng/stat/smstat/dayquot/d{{date_code}}e.htm"

REGULAR_STOCK_THRESHOLD = 10000
