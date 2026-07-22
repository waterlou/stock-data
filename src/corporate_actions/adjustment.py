import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional

from src.models.schemas import CorporateAction, AdjustedQuote
from src.database import queries

logger = logging.getLogger(__name__)


def compute_adjusted_quotes(stock_code: str) -> List[AdjustedQuote]:
    raw_quotes = queries.get_all_quotations_for_stock(stock_code)
    corporate_actions = queries.get_corporate_actions_for_stock(stock_code)

    if not raw_quotes:
        return []

    sorted_quotes = sorted(raw_quotes, key=lambda q: q["trade_date"], reverse=True)

    action_index = len(corporate_actions) - 1

    adjustment_factor = 1.0
    adjusted_quotes = []

    for quote in sorted_quotes:
        trade_date = quote["trade_date"]
        closing = quote["closing"]
        high = quote["high"]
        low = quote["low"]
        opening = quote.get("opening")
        volume = quote.get("shares_traded", 0) or 0

        while action_index >= 0:
            action = corporate_actions[action_index]
            if action.action_date <= trade_date:
                break

            if action.action_type == "split" and action.split_ratio:
                adjustment_factor *= action.split_ratio
            elif action.action_type == "dividend" and action.dividend_amount:
                if closing and float(closing) > 0:
                    factor = (float(closing) - action.dividend_amount) / float(closing)
                    adjustment_factor *= factor

            action_index -= 1

        if adjustment_factor != 1.0 and closing:
            adj_close = Decimal(str(float(closing) * adjustment_factor))
            adj_high = Decimal(str(float(high) * adjustment_factor)) if high else adj_close
            adj_low = Decimal(str(float(low) * adjustment_factor)) if low else adj_close
            adj_open = Decimal(str(float(opening) * adjustment_factor)) if opening else adj_close
            adj_volume = int(volume / adjustment_factor) if adjustment_factor > 0 else int(volume)
        else:
            adj_close = closing
            adj_high = high
            adj_low = low
            adj_open = opening or closing
            adj_volume = int(volume)

        if adj_close is None:
            continue

        adjusted_quotes.append(AdjustedQuote(
            stock_code=stock_code,
            trade_date=trade_date,
            adj_open=adj_open if adj_open else adj_close,
            adj_high=adj_high if adj_high else adj_close,
            adj_low=adj_low if adj_low else adj_close,
            adj_close=adj_close,
            adj_volume=int(adj_volume),
            adjustment_factor=adjustment_factor,
        ))

    return adjusted_quotes


def recompute_all_adjusted():
    from src.database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT stock_code FROM daily_quotations")
        codes = [row[0] for row in cur.fetchall()]

    logger.info("Recomputing adjusted prices for %d stocks", len(codes))

    for code in codes:
        try:
            adjusted = compute_adjusted_quotes(code)
            if adjusted:
                queries.upsert_adjusted_quotations(adjusted)
        except Exception as e:
            logger.error("Failed to compute adjusted quotes for %s: %s", code, e)

    logger.info("Adjusted prices recomputed")
