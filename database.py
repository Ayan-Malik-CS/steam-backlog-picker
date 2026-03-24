import sqlite3
from datetime import datetime, timedelta

CACHE_TTL_HOURS = 24

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # This lets us access columns by name
    return conn

def init_db():
    conn = get_db_connection()
    with open('schema.sql') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

def save_games_to_db(steam_id, games_list):
    conn = get_db_connection()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    for game in games_list:
        conn.execute('''
            INSERT OR REPLACE INTO games (steam_id, appid, name, playtime_forever, img_icon_url, is_free, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (steam_id, game['appid'], game['name'], game['playtime_forever'], game.get('img_icon_url', ''), 1 if game.get('is_free') else 0, now))
    conn.commit()
    conn.close()

def is_cache_stale(steam_id):
    """Returns True if there are no cached games, or if the cache is older than CACHE_TTL_HOURS."""
    conn = get_db_connection()
    row = conn.execute(
        'SELECT last_updated FROM games WHERE steam_id = ? ORDER BY last_updated DESC LIMIT 1',
        (steam_id,)
    ).fetchone()
    conn.close()

    if not row:
        return True

    last_updated = datetime.strptime(row['last_updated'], '%Y-%m-%d %H:%M:%S')
    return datetime.utcnow() - last_updated > timedelta(hours=CACHE_TTL_HOURS)


def get_active_games(steam_id):
    conn = get_db_connection()
    games = conn.execute('SELECT * FROM games WHERE steam_id = ? AND is_ignored = 0', (steam_id,)).fetchall()
    conn.close()
    return games

def get_cached_games(steam_id):
    conn = get_db_connection()
    games = conn.execute('SELECT * FROM games WHERE steam_id = ?', (steam_id,)).fetchall()
    conn.close()
    return games

def get_ignored_games(steam_id):
    conn = get_db_connection()
    games = conn.execute('SELECT * FROM games WHERE steam_id = ? AND is_ignored = 1', (steam_id,)).fetchall()
    conn.close()
    return games