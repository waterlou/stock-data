import time
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BACKOFF = 5


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
                logger.error("All retries exhausted for %s", url)
                raise
    return None
