# Stock Data

Multi-market stock data service (HK + US) with multiple data sources (HKEX, Yahoo Finance), daily batch downloads, and on-demand fetching with database caching.

## Quick Start

```bash
docker compose up -d
```

- Web UI: http://localhost:8000
- API docs: http://localhost:8000/docs

## How It Works

- **Batch jobs** — HK daily snapshot at 17:00 HKT (HKEX), US watchlist at 06:00 HKT (Yahoo)
- **On-demand** — if the API finds data not in the database, it queues a fetch and returns `202`; retry in ~30s and the data is served from the DB cache
- **Source priority** — per-market source ordering (`market_sources` table). HK: hkex → yahoo; US: yahoo
- **Ticker normalization** — all tickers stored in Yahoo format. `700`, `0700`, `00700`, `700.HK`, `00700.HK` all resolve to `0700.HK`; `aapl` → `AAPL`

## Watchlist

US batch downloads only track stocks on the watchlist. Manage via the **Watchlist** tab in the UI (add / import CSV / export / remove).

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/overview` | Dashboard stats |
| `GET /api/markets` | Available markets (HK, US) |
| `GET /api/sources` | Data sources + per-market priority |
| `GET /api/stocks` | List stocks (`?search=`, `?market=`, `?watchlist=`) |
| `GET /api/stocks/{ticker}/prices` | Daily OHLCV (`?from_date=`, `?to_date=`) — returns `202` if queued |
| `GET /api/stocks/{ticker}/corporate-actions` | Splits & dividends |
| `GET /api/stocks/{ticker}/fundamentals` | Market cap, P/E, EPS, sector |
| `GET /api/indices` | Market indices (HSI, S&P 500) |
| `GET /api/short-selling` | HKEX short selling |
| `GET /api/watchlist` | List / add / remove / import / export |
| `GET /api/queue` | On-demand download queue status |
| `GET /api/logs` | Batch & on-demand job logs |

Ticker params are forgiving: `0700.HK`, `00700.HK`, `700` all work.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://water@localhost:5432/hkex` | PostgreSQL connection |
| `SCRAPE_TIME_HK` | `17:00` | HK daily batch time (HKT) |
| `SCRAPE_TIME_US` | `06:00` | US daily batch time (HKT) |
| `TZ` | `Asia/Hong_Kong` | Timezone |
| `LOG_LEVEL` | `INFO` | Logging level |
| `WORKER_POLL_INTERVAL` | `5` | On-demand queue poll interval (s) |
