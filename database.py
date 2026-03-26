import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

CACHE_TTL_HOURS = 24
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    with open('schema.sql') as f:
        cur.execute(f.read())
    conn.commit()
    cur.close()
    conn.close()

def save_games_to_db(steam_id, games_list):
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.utcnow()
    for game in games_list:
        cur.execute('''
            INSERT INTO games (steam_id, appid, name, playtime_forever, img_icon_url, is_free, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (steam_id, appid) DO UPDATE SET
                name = EXCLUDED.name,
                playtime_forever = EXCLUDED.playtime_forever,
                img_icon_url = EXCLUDED.img_icon_url,
                is_free = EXCLUDED.is_free,
                last_updated = EXCLUDED.last_updated
        ''', (
            steam_id,
            game['appid'],
            game['name'],
            game['playtime_forever'],
            game.get('img_icon_url', ''),
            1 if game.get('is_free') else 0,
            now
        ))
    conn.commit()
    cur.close()
    conn.close()

def is_cache_stale(steam_id):
    """Returns True if there are no cached games, or if the cache is older than CACHE_TTL_HOURS."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        'SELECT last_updated FROM games WHERE steam_id = %s ORDER BY last_updated DESC LIMIT 1',
        (steam_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return True

    last_updated = row['last_updated']
    if isinstance(last_updated, str):
        last_updated = datetime.strptime(last_updated, '%Y-%m-%d %H:%M:%S')
    return datetime.utcnow() - last_updated.replace(tzinfo=None) > timedelta(hours=CACHE_TTL_HOURS)

def _fetch_all(query, params):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_active_games(steam_id):
    return _fetch_all(
        'SELECT * FROM games WHERE steam_id = %s AND is_ignored = 0 AND is_played = 0',
        (steam_id,)
    )

def get_cached_games(steam_id):
    return _fetch_all(
        'SELECT * FROM games WHERE steam_id = %s',
        (steam_id,)
    )

def get_ignored_games(steam_id):
    return _fetch_all(
        'SELECT * FROM games WHERE steam_id = %s AND is_ignored = 1',
        (steam_id,)
    )

def get_played_games(steam_id):
    return _fetch_all(
        'SELECT * FROM games WHERE steam_id = %s AND is_played = 1',
        (steam_id,)
    )