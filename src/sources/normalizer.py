from typing import Optional


def normalize_ticker(value: str, market: str = "") -> str:
    """Normalize a user-supplied ticker to canonical Yahoo format.

    HK: "700", "0700", "00700", "700.HK", "00700.HK" -> "0700.HK"
    US: "aapl", "AAPL.US" -> "AAPL"
    """
    value = value.upper().strip()
    if not value:
        raise ValueError("Empty ticker")

    if value.endswith(".HK"):
        market = "HK"
    elif value.endswith(".US"):
        market = "US"
    elif not market:
        market = "HK" if value.isdigit() else "US"

    if market == "HK":
        code = value.replace(".HK", "")
        if code.isdigit():
            code = code.lstrip("0") or "0"
            code = code.zfill(4)
        return f"{code}.HK"
    if market == "US":
        return value.replace(".US", "")
    raise ValueError(f"Unknown market: {market}")


def market_from_ticker(ticker: str) -> Optional[str]:
    ticker = ticker.upper().strip()
    if ticker.endswith(".HK"):
        return "HK"
    if ticker.endswith(".US"):
        return "US"
    return None


def ticker_market_suffix(market: str) -> str:
    return ".HK" if market == "HK" else ""
