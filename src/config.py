import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hkex:hkex@localhost:5432/hkex")
SCRAPE_TIME_HK = os.getenv("SCRAPE_TIME_HK", "17:00")
SCRAPE_TIME_US = os.getenv("SCRAPE_TIME_US", "06:00")
TZ = os.getenv("TZ", "Asia/Hong_Kong")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
WORKER_POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
INTRADAY_RETENTION_DAYS = int(os.getenv("INTRADAY_RETENTION_DAYS", "30"))
INTRADAY_RECENCY_MINUTES = int(os.getenv("INTRADAY_RECENCY_MINUTES", "15"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
API_KEY = os.getenv("API_KEY", "")

HKEX_BASE_URL = "https://www.hkex.com.hk"
HKEX_CALENDAR_URL = f"{HKEX_BASE_URL}/eng/stat/smstat/dayquot/qtn.asp"
HKEX_DAILY_URL_TEMPLATE = f"{HKEX_BASE_URL}/eng/stat/smstat/dayquot/d{{date_code}}e.htm"

REGULAR_STOCK_THRESHOLD = 10000
