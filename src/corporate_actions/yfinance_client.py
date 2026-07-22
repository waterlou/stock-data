import logging
from datetime import date, datetime
from typing import List, Optional

import yfinance as yf

from src.models.schemas import CorporateAction

logger = logging.getLogger(__name__)


def stock_code_to_yfinance(code: str) -> str:
    return f"{int(code):04d}.HK"


def fetch_corporate_actions(stock_code: str) -> List[CorporateAction]:
    ticker = stock_code_to_yfinance(stock_code)
    actions = []

    try:
        t = yf.Ticker(ticker)
    except Exception as e:
        logger.warning("Failed to create yfinance ticker for %s: %s", ticker, e)
        return actions

    try:
        splits = t.splits
        if splits is not None and len(splits) > 0:
            for dt, ratio in splits.items():
                if isinstance(dt, datetime):
                    action_date = dt.date()
                else:
                    action_date = dt

                try:
                    ratio_float = float(ratio)
                except (ValueError, TypeError):
                    continue

                actions.append(CorporateAction(
                    stock_code=stock_code,
                    action_date=action_date,
                    action_type="split",
                    split_ratio=ratio_float,
                ))
    except Exception as e:
        logger.debug("No splits for %s: %s", stock_code, e)

    try:
        dividends = t.dividends
        if dividends is not None and len(dividends) > 0:
            for dt, amount in dividends.items():
                if isinstance(dt, datetime):
                    action_date = dt.date()
                else:
                    action_date = dt

                try:
                    amount_float = float(amount)
                except (ValueError, TypeError):
                    continue

                if amount_float <= 0:
                    continue

                actions.append(CorporateAction(
                    stock_code=stock_code,
                    action_date=action_date,
                    action_type="dividend",
                    dividend_amount=amount_float,
                ))
    except Exception as e:
        logger.debug("No dividends for %s: %s", stock_code, e)

    actions.sort(key=lambda a: a.action_date)
    return actions


def fetch_actions_batch(stock_codes: List[str]) -> List[CorporateAction]:
    all_actions = []
    for code in stock_codes:
        try:
            actions = fetch_corporate_actions(code)
            all_actions.extend(actions)
        except Exception as e:
            logger.warning("Failed to fetch corporate actions for %s: %s", code, e)
    return all_actions
