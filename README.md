# HKEX Stock Data

HKEX daily quotation scraper with PostgreSQL storage, REST API, and web UI for browsing data.

## Quick Start

```bash
docker compose up -d
```

- Web UI: http://localhost:8000
- API docs: http://localhost:8000/docs

## Services

| Service | Port | Description |
|---------|------|-------------|
| `web` | 8000 | FastAPI server + web UI |
| `scraper` | — | Daily scraper, runs at 17:00 HKT |
| `postgres` | 5432 | PostgreSQL 16 database |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/overview` | Dashboard stats |
| `GET /api/stocks` | List stocks (`?search=`, `?status=`, pagination) |
| `GET /api/stocks/{code}` | Stock detail |
| `GET /api/stocks/{code}/quotations` | Daily prices (`?from_date=`, `?to_date=`) |
| `GET /api/stocks/{code}/adjusted` | Split/dividend-adjusted prices |
| `GET /api/stocks/{code}/corporate-actions` | Splits & dividends |
| `GET /api/market-highlights` | HSI, HSCEI index data |
| `GET /api/short-selling` | Short selling (`?stock_code=`, `?trade_date=`) |
| `GET /api/dates` | Available trading dates |
| `GET /api/scrape-logs` | Scrape job history |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://hkex:hkex@localhost:5432/hkex` | PostgreSQL connection |
| `SCRAPE_TIME` | `17:00` | Daily scrape time (HKT) |
| `TZ` | `Asia/Hong_Kong` | Timezone |
| `LOG_LEVEL` | `INFO` | Logging level |
