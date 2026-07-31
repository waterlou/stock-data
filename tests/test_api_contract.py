import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_new_query_functions_exist():
    from src.database import queries
    assert callable(getattr(queries, "upsert_stocks_bulk", None))
    assert callable(getattr(queries, "refresh_stock_dates_bulk", None))
    assert callable(getattr(queries, "last_fetch_status", None))


def test_data_endpoints_accept_force():
    from src.api import server
    for name in ("stock_prices", "stock_intraday", "stock_corporate_actions", "stock_fundamentals"):
        fn = getattr(server, name)
        assert "force" in fn.__code__.co_varnames, f"{name} missing force param"
    assert callable(getattr(server, "_data_fetch_response", None))
