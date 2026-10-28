ALTER TABLE positions ADD COLUMN IF NOT EXISTS vertical_rate DOUBLE PRECISION;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS squawk TEXT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS type_code TEXT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS registration TEXT;
-- Reproduccion historica: buscar por instante
CREATE INDEX IF NOT EXISTS positions_time ON positions (time_position);

-- Resumenes por hora: sobreviven a la retencion de posiciones
CREATE TABLE IF NOT EXISTS hourly_stats (
    hour TIMESTAMPTZ PRIMARY KEY,
    flights INTEGER NOT NULL,
    positions INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS hourly_airlines (
    hour TIMESTAMPTZ NOT NULL,
    airline TEXT NOT NULL,
    flights INTEGER NOT NULL,
    PRIMARY KEY (hour, airline)
);

-- Lista de seguimiento y alertas
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('callsign', 'icao24', 'registration', 'squawk')),
    value TEXT NOT NULL,
    label TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (kind, value)
);
CREATE TABLE IF NOT EXISTS alert_events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind TEXT NOT NULL,
    watch_id INTEGER,
    icao24 TEXT,
    callsign TEXT,
    message TEXT NOT NULL
);
