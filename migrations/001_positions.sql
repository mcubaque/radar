CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    icao24 TEXT NOT NULL,
    callsign TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION,
    velocity DOUBLE PRECISION,
    heading DOUBLE PRECISION,
    on_ground BOOLEAN,
    time_position BIGINT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (icao24, time_position)
);
CREATE INDEX IF NOT EXISTS positions_icao_time ON positions (icao24, recorded_at DESC);
