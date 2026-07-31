"""LEAN and lean-hybrid CSV export builders.

Daily:  single zip -> {ticker}.csv,  lines "YYYYMMDD 00:00,O,H,L,C,V"
Hybrid intraday: single zip -> {ticker}.csv, lines "YYYYMMDD HH:MM,O,H,L,C,V"
Strict LEAN intraday: outer zip of per-date {YYYYMMDD}_trade.zip, each with
  trade.csv of "ms_since_midnight,O,H,L,C,V"
"""
import io
import zipfile


def _num(v):
    if v is None:
        return ""
    return f"{float(v):.8f}".rstrip("0").rstrip(".")


def _csv_line(r, time_str):
    open_v = r.get("open", r.get("close"))
    if open_v is None:
        open_v = r.get("close")
    return f"{time_str},{_num(open_v)},{_num(r.get('high'))},{_num(r.get('low'))},{_num(r.get('close'))},{int(r.get('volume') or 0)}"


def _zip_single(filename: str, csv: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, csv)
    return buf.getvalue()


def lean_daily_zip(rows, ticker: str) -> bytes:
    """Daily rows -> single {ticker}.zip with YYYYMMDD 00:00,O,H,L,C,V."""
    lines = []
    for r in sorted(rows, key=lambda x: x["trade_date"]):
        lines.append(_csv_line(r, f"{r['trade_date']:%Y%m%d} 00:00"))
    return _zip_single(f"{ticker}.csv", "\n".join(lines) + "\n")


def lean_hybrid_intraday_zip(rows, ticker: str) -> bytes:
    """Intraday rows -> single {ticker}.zip with YYYYMMDD HH:MM,O,H,L,C,V."""
    lines = []
    for r in sorted(rows, key=lambda x: x["date_time"]):
        lines.append(_csv_line(r, f"{r['date_time']:%Y%m%d %H:%M}"))
    return _zip_single(f"{ticker}.csv", "\n".join(lines) + "\n")


def lean_intraday_zip(rows, ticker: str) -> bytes:
    """Intraday rows -> outer zip of per-date {YYYYMMDD}_trade.zip (ms-since-midnight)."""
    groups = {}
    for r in rows:
        dt = r["date_time"]
        groups.setdefault(f"{dt:%Y%m%d}", []).append(r)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as outer:
        for date_key in sorted(groups):
            lines = []
            for r in sorted(groups[date_key], key=lambda x: x["date_time"]):
                dt = r["date_time"]
                ms = int((dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000)
                lines.append(_csv_line(r, str(ms)))
            outer.writestr(f"{date_key}_trade.zip",
                           _zip_single("trade.csv", "\n".join(lines) + "\n"))
    return buf.getvalue()
