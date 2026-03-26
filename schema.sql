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