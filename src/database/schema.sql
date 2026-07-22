CREATE TABLE IF NOT EXISTS stock_master (
    stock_code       VARCHAR(10) PRIMARY KEY,
    stock_name       VARCHAR(200),
    first_trade_date DATE,
    last_trade_date  DATE,
    status           VARCHAR(20) DEFAULT 'active',
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stock_name_history (
    stock_code       VARCHAR(10),
    stock_name       VARCHAR(200),
    first_seen_date  DATE,
    last_seen_date   DATE,
    PRIMARY KEY (stock_code, first_seen_date)
);

CREATE TABLE IF NOT EXISTS daily_quotations (
    trade_date       DATE,
    stock_code       VARCHAR(10),
    stock_name       VARCHAR(200),
    currency         VARCHAR(5),
    prev_close       NUMERIC,
    closing          NUMERIC,
    ask              NUMERIC,
    bid              NUMERIC,
    high             NUMERIC,
    low              NUMERIC,
    shares_traded    BIGINT,
    turnover         NUMERIC,
    PRIMARY KEY (trade_date, stock_code)
);

CREATE INDEX IF NOT EXISTS idx_daily_quotations_code
    ON daily_quotations (stock_code, trade_date);

CREATE TABLE IF NOT EXISTS market_highlights (
    trade_date                 DATE PRIMARY KEY,
    hsi_close                  NUMERIC,
    hsi_change                 NUMERIC,
    hsi_change_pct             NUMERIC,
    hscei_close                NUMERIC,
    hscei_change               NUMERIC,
    hscei_change_pct           NUMERIC,
    hscci_close                NUMERIC,
    hscci_change               NUMERIC,
    hscci_change_pct           NUMERIC,
    sphkex_largecap_close      NUMERIC,
    sphkex_largecap_change     NUMERIC,
    sphkex_largecap_change_pct NUMERIC,
    securities_traded          INTEGER,
    advanced                   INTEGER,
    declined                   INTEGER,
    unchanged                  INTEGER,
    turnover_hkd               NUMERIC,
    turnover_shares            BIGINT,
    turnover_deals             INTEGER,
    rmb_turnover               NUMERIC
);

CREATE TABLE IF NOT EXISTS short_selling (
    trade_date      DATE,
    stock_code      VARCHAR(10),
    stock_name      VARCHAR(200),
    short_shares    BIGINT,
    short_turnover  NUMERIC,
    total_shares    BIGINT,
    total_turnover  NUMERIC,
    PRIMARY KEY (trade_date, stock_code)
);

CREATE INDEX IF NOT EXISTS idx_short_selling_code
    ON short_selling (stock_code, trade_date);

CREATE TABLE IF NOT EXISTS corporate_actions (
    id               SERIAL PRIMARY KEY,
    stock_code       VARCHAR(10),
    action_date      DATE,
    action_type      VARCHAR(20),
    split_ratio      NUMERIC,
    dividend_amount  NUMERIC,
    source           VARCHAR(50) DEFAULT 'yfinance',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (stock_code, action_date, action_type)
);

CREATE TABLE IF NOT EXISTS daily_quotations_adjusted (
    trade_date          DATE,
    stock_code          VARCHAR(10),
    adj_open            NUMERIC,
    adj_high            NUMERIC,
    adj_low             NUMERIC,
    adj_close           NUMERIC,
    adj_volume          BIGINT,
    adjustment_factor   DOUBLE PRECISION,
    PRIMARY KEY (trade_date, stock_code)
);

CREATE INDEX IF NOT EXISTS idx_adj_quotations_code
    ON daily_quotations_adjusted (stock_code, trade_date);

CREATE TABLE IF NOT EXISTS scrape_log (
    id            SERIAL PRIMARY KEY,
    trade_date    DATE,
    section       VARCHAR(50),
    status        VARCHAR(20),
    rows_inserted INTEGER,
    error_message TEXT,
    started_at    TIMESTAMPTZ DEFAULT NOW(),
    completed_at  TIMESTAMPTZ
);
