from typing import Optional


def normalize_ticker(value: str, market: str = "") -> str:
    """Normalize a user-supplied ticker to canonical form.

    HK: "700", "0700", "00700", "700.HK", "00700.HK" -> "0700.HK"
    US: "aapl", "AAPL.US" -> "AAPL"
    CN: "600519", "600519.SH", "sh600519" -> "600519.SH"
        "000001", "sz000001" -> "000001.SZ"
    """
    value = value.upper().strip()
    if not value:
        raise ValueError("Empty ticker")

    if value.endswith(".HK"):
        market = "HK"
    elif value.endswith(".US"):
        market = "US"
    elif value.endswith((".SH", ".SZ")):
        market = "CN"
    elif value.startswith(("SH", "SZ")):
        market = "CN"
    elif not market:
        if value.isdigit():
            market = "HK" if len(value) < 6 else "CN"
        else:
            market = "US"

    if market == "HK":
        code = value.replace(".HK", "")
        if code.isdigit():
            code = code.lstrip("0") or "0"
            code = code.zfill(4)
        return f"{code}.HK"
    if market == "US":
        return value.replace(".US", "")
    if market == "CN":
        return _normalize_cn(value)
    raise ValueError(f"Unknown market: {market}")


def _normalize_cn(value: str) -> str:
    if value.startswith("SH"):
        return f"{value[2:].zfill(6)}.SH"
    if value.startswith("SZ"):
        return f"{value[2:].zfill(6)}.SZ"
    code = value.replace(".SH", "").replace(".SZ", "")
    if code.isdigit():
        code = code.zfill(6)
        if code.startswith(("6", "9")):
            return f"{code}.SH"
        return f"{code}.SZ"
    return value


def market_from_ticker(ticker: str) -> Optional[str]:
    ticker = ticker.upper().strip()
    if ticker.endswith(".HK"):
        return "HK"
    if ticker.endswith(".US"):
        return "US"
    if ticker.endswith((".SH", ".SZ")) or ticker.startswith(("SH", "SZ")):
        return "CN"
    return None


def ticker_market_suffix(market: str) -> str:
    if market == "HK":
        return ".HK"
    if market == "US":
        return ""
    if market == "CN":
        return ""
    return ""
