CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    steam_id TEXT NOT NULL,
    appid INTEGER NOT NULL,
    name TEXT NOT NULL,
    playtime_forever INTEGER NOT NULL,
    img_icon_url TEXT,
    is_ignored BOOLEAN DEFAULT 0,
    is_free BOOLEAN DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hltb_hours REAL
);