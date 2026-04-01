CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY,
    steam_id TEXT NOT NULL,
    appid INTEGER NOT NULL,
    name TEXT NOT NULL,
    playtime_forever INTEGER NOT NULL,
    img_icon_url TEXT,
    is_ignored BOOLEAN DEFAULT FALSE,
    is_free BOOLEAN DEFAULT FALSE,
    is_played BOOLEAN DEFAULT FALSE,
    last_updated TIMESTAMP DEFAULT NOW(),
    hltb_hours REAL,
    genres TEXT,
    UNIQUE (steam_id, appid)
);

CREATE TABLE IF NOT EXISTS sync_metadata (
    key TEXT PRIMARY KEY,
    hltb_sync_time TIMESTAMP,
    free_sync_time TIMESTAMP,
    genre_sync_time TIMESTAMP,
    library_sync_time TIMESTAMP
);