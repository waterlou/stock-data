-- Markets
CREATE TABLE IF NOT EXISTS markets (
    market_code VARCHAR(10) PRIMARY KEY,
    market_name VARCHAR(100) NOT NULL,
    currency   VARCHAR(5) NOT NULL,
    timezone   VARCHAR(50) NOT NULL
);

-- Data sources
CREATE TABLE IF NOT EXISTS data_sources (
    source_code VARCHAR(20) PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    enabled     BOOLEAN DEFAULT TRUE
);

-- Per-market source priority (lower number = tried first)
CREATE TABLE IF NOT EXISTS market_sources (
    market_code VARCHAR(10) NOT NULL REFERENCES markets(market_code),
    source_code VARCHAR(20) NOT NULL REFERENCES data_sources(source_code),
    priority    INT NOT NULL,
    PRIMARY KEY (market_code, source_code)
);

-- Stocks (canonical ticker is Yahoo format: 0700.HK, AAPL)
CREATE TABLE IF NOT EXISTS stocks (
    id             SERIAL PRIMARY KEY,
    market_code    VARCHAR(10) NOT NULL REFERENCES markets(market_code),
    ticker         VARCHAR(20) NOT NULL,
    name           VARCHAR(500),
    watchlist      BOOLEAN DEFAULT FALSE,
    status         VARCHAR(20) DEFAULT 'active',
    first_date     DATE,
    last_date      DATE,
    last_fetched_at TIMESTAMPTZ,
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (market_code, ticker)
);

-- Daily OHLCV prices (one canonical row per stock per day, tagged with source)
CREATE TABLE IF NOT EXISTS daily_prices (
    trade_date  DATE NOT NULL,
    stock_id    INT NOT NULL REFERENCES stocks(id),
    source_code VARCHAR(20) NOT NULL REFERENCES data_sources(source_code),
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    adj_close   NUMERIC,
    volume      BIGINT,
    prev_close  NUMERIC,
    bid         NUMERIC,
    ask         NUMERIC,
    currency    VARCHAR(5),
    PRIMARY KEY (trade_date, stock_id)
);
CREATE INDEX IF NOT EXISTS idx_daily_prices_stock ON daily_prices (stock_id, trade_date);

-- Market indices (HSI, S&P 500, ...)
CREATE TABLE IF NOT EXISTS market_indices (
    trade_date  DATE NOT NULL,
    market_code VARCHAR(10) NOT NULL REFERENCES markets(market_code),
    index_code  VARCHAR(20) NOT NULL,
    index_name  VARCHAR(200),
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    change      NUMERIC,
    change_pct  NUMERIC,
    source_code VARCHAR(20) NOT NULL REFERENCES data_sources(source_code),
    PRIMARY KEY (trade_date, market_code, index_code)
);

-- HKEX short selling
CREATE TABLE IF NOT EXISTS short_selling (
    trade_date     DATE NOT NULL,
    stock_id       INT NOT NULL REFERENCES stocks(id),
    source_code    VARCHAR(20) NOT NULL REFERENCES data_sources(source_code),
    short_shares   BIGINT,
    short_turnover NUMERIC,
    total_shares   BIGINT,
    total_turnover NUMERIC,
    PRIMARY KEY (trade_date, stock_id)
);
CREATE INDEX IF NOT EXISTS idx_short_selling_stock ON short_selling (stock_id, trade_date);

-- Corporate actions (splits, dividends)
CREATE TABLE IF NOT EXISTS corporate_actions (
    id              SERIAL PRIMARY KEY,
    stock_id        INT NOT NULL REFERENCES stocks(id),
    action_date     DATE NOT NULL,
    action_type     VARCHAR(20) NOT NULL,
    split_ratio     NUMERIC,
    dividend_amount NUMERIC,
    source_code     VARCHAR(20) NOT NULL REFERENCES data_sources(source_code),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (stock_id, action_date, action_type)
);

-- Fundamentals snapshot (US)
CREATE TABLE IF NOT EXISTS fundamentals (
    stock_id       INT NOT NULL REFERENCES stocks(id),
    report_date    DATE NOT NULL,
    source_code    VARCHAR(20) NOT NULL REFERENCES data_sources(source_code),
    market_cap     NUMERIC,
    pe_ratio       NUMERIC,
    eps            NUMERIC,
    dividend_yield NUMERIC,
    sector         VARCHAR(200),
    industry       VARCHAR(200),
    PRIMARY KEY (stock_id, report_date, source_code)
);

-- Intraday OHLCV bars (5m default, on-demand) - partitioned by month
CREATE TABLE IF NOT EXISTS intraday_prices (
    date_time    TIMESTAMPTZ NOT NULL,
    stock_id     INT NOT NULL REFERENCES stocks(id),
    source_code  VARCHAR(20) NOT NULL REFERENCES data_sources(source_code),
    interval_min INT NOT NULL DEFAULT 5,
    open         NUMERIC,
    high         NUMERIC,
    low          NUMERIC,
    close        NUMERIC,
    volume       BIGINT,
    PRIMARY KEY (date_time, stock_id, interval_min)
) PARTITION BY RANGE (date_time);
CREATE INDEX IF NOT EXISTS idx_intraday_stock ON intraday_prices (stock_id, interval_min, date_time);

-- Source health tracking (consecutive failures mark a source unhealthy)
CREATE TABLE IF NOT EXISTS source_health (
    source_code         VARCHAR(20) PRIMARY KEY REFERENCES data_sources(source_code),
    consecutive_failures INT DEFAULT 0,
    last_success_at     TIMESTAMPTZ,
    last_failure_at     TIMESTAMPTZ,
    last_error          TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- On-demand download queue
CREATE TABLE IF NOT EXISTS download_queue (
    id            SERIAL PRIMARY KEY,
    market_code   VARCHAR(10) NOT NULL,
    ticker        VARCHAR(20) NOT NULL,
    data_type     VARCHAR(20) NOT NULL,
    status        VARCHAR(20) DEFAULT 'pending',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_queue_status ON download_queue (status, created_at);
CREATE INDEX IF NOT EXISTS idx_queue_recent ON download_queue (market_code, ticker, data_type, status, completed_at);
-- Only one in-flight request per (market, ticker, type)
CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_dedup ON download_queue (market_code, ticker, data_type)
    WHERE status IN ('pending', 'processing');

-- Job logs
CREATE TABLE IF NOT EXISTS scan_logs (
    id              SERIAL PRIMARY KEY,
    market_code     VARCHAR(10),
    source_code     VARCHAR(20),
    scan_type       VARCHAR(20),
    status          VARCHAR(20),
    items_processed INT,
    items_inserted  INT,
    error_message   TEXT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- Seed reference data
INSERT INTO markets (market_code, market_name, currency, timezone) VALUES
    ('HK', 'Hong Kong', 'HKD', 'Asia/Hong_Kong'),
    ('US', 'United States', 'USD', 'America/New_York'),
    ('CN', 'China', 'CNY', 'Asia/Shanghai')
ON CONFLICT (market_code) DO NOTHING;

INSERT INTO data_sources (source_code, source_name) VALUES
    ('hkex', 'HKEX'),
    ('yahoo', 'Yahoo Finance'),
    ('tencent', 'Tencent Finance'),
    ('aastocks', 'AASTOCKS'),
    ('akshare', 'AKShare')
ON CONFLICT (source_code) DO NOTHING;

INSERT INTO market_sources (market_code, source_code, priority) VALUES
    ('HK', 'hkex', 1),
    ('HK', 'yahoo', 2),
    ('HK', 'tencent', 3),
    ('HK', 'aastocks', 4),
    ('HK', 'akshare', 5),
    ('US', 'yahoo', 1),
    ('US', 'akshare', 2),
    ('CN', 'tencent', 1),
    ('CN', 'akshare', 2)
ON CONFLICT (market_code, source_code) DO NOTHING;
