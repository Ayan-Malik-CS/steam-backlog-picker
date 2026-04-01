from flask import Flask, render_template, request, jsonify, session, flash, redirect, url_for
from steam_api import get_steam_library, resolve_vanity_url, PrivateProfileError
from database import get_active_games, save_games_to_db, get_db_connection, get_ignored_games, get_played_games, is_cache_stale, init_db, get_sync_metadata, update_sync_time
import time
import threading
import requests
import os
import psycopg2
import psycopg2.extras

app = Flask(__name__)

secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    raise RuntimeError("SECRET_KEY environment variable is not set. Generate one with: python -c \"import secrets; print(secrets.token_hex())\"")
app.secret_key = secret_key

init_db()

# --- THE HOMEPAGE ---
@app.route('/')
def index():
    return render_template('index.html')

# --- THE BACKLOG DISPLAY ---
@app.route('/backlog', methods=['POST'])
def show_backlog():
    user_input = request.form.get('steam_id_input')

    if not (user_input.isdigit() and len(user_input) == 17):
        steam_id = resolve_vanity_url(user_input)
    else:
        steam_id = user_input

    if not steam_id:
        flash("User not found. Please check your Steam ID or custom URL name.")
        return redirect(url_for('index'))

    session['steam_id'] = steam_id

    if is_cache_stale(steam_id):
        try:
            steam_games = get_steam_library(steam_id)
            save_games_to_db(steam_id, steam_games)
        except PrivateProfileError as e:
            return render_template('private.html', steam_id=e.steam_id)
        except ConnectionError as e:
            flash(str(e))
            return redirect(url_for('index'))

    games = get_active_games(steam_id)
    ignored_games = get_ignored_games(steam_id)
    played_games = get_played_games(steam_id)

    # Build sorted list of unique genres across all games
    all_genres = set()
    for game in games:
        if game['genres']:
            for g in game['genres'].split(','):
                all_genres.add(g.strip())
    all_genres = sorted(all_genres)

    sync_metadata = get_sync_metadata()

    return render_template('dashboard.html', games=games, ignored_games=ignored_games, played_games=played_games, steam_id=steam_id, all_genres=all_genres, sync_metadata=sync_metadata)

def _run_update(sql, params):
    """Helper for simple UPDATE queries."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    cur.close()
    conn.close()

@app.route('/mark_played/<int:appid>', methods=['POST'])
def mark_played(appid):
    steam_id = session.get('steam_id')
    if not steam_id:
        return jsonify({"error": "Session expired"}), 401
    _run_update('UPDATE games SET is_played = TRUE WHERE appid = %s AND steam_id = %s', (appid, steam_id))
    return jsonify({"success": True}), 200

@app.route('/unmark_played/<int:appid>', methods=['POST'])
def unmark_played(appid):
    steam_id = session.get('steam_id')
    if not steam_id:
        return jsonify({"error": "Session expired"}), 401
    _run_update('UPDATE games SET is_played = FALSE WHERE appid = %s AND steam_id = %s', (appid, steam_id))
    return jsonify({"success": True}), 200

@app.route('/ignore/<int:appid>', methods=['POST'])
def ignore_game(appid):
    steam_id = session.get('steam_id')
    if not steam_id:
        return jsonify({"error": "Session expired"}), 401
    _run_update('UPDATE games SET is_ignored = TRUE WHERE appid = %s AND steam_id = %s', (appid, steam_id))
    return jsonify({"success": True}), 200

@app.route('/dashboard')
def dashboard():
    steam_id = session.get('steam_id')
    if not steam_id:
        return redirect(url_for('index'))
    games = get_active_games(steam_id)
    ignored_games = get_ignored_games(steam_id)
    played_games = get_played_games(steam_id)
    all_genres = set()
    for game in games:
        if game['genres']:
            for g in game['genres'].split(','):
                all_genres.add(g.strip())
    all_genres = sorted(all_genres)
    sync_metadata = get_sync_metadata()
    return render_template('dashboard.html', games=games, ignored_games=ignored_games, played_games=played_games, steam_id=steam_id, all_genres=all_genres, sync_metadata=sync_metadata)

# --- THE PICKER MENU ---
@app.route('/picker')
def picker():
    steam_id = session.get('steam_id')
    if not steam_id:
        flash("Please load your backlog first.")
        return redirect(url_for('index'))
    games = get_active_games(steam_id)
    return render_template('picker.html', games=games)

@app.route('/unignore/<int:appid>', methods=['POST'])
def unignore_game(appid):
    steam_id = session.get('steam_id')
    if not steam_id:
        return jsonify({"error": "Session expired"}), 401
    _run_update('UPDATE games SET is_ignored = FALSE WHERE appid = %s AND steam_id = %s', (appid, steam_id))
    return jsonify({"success": True}), 200

sync_status = {"running": False, "updated": 0, "total": 0, "processed": 0}
free_sync_status = {"running": False, "updated": 0, "total": 0, "processed": 0}

def search_hltb_by_name(game_name, appid=None):
    """Search HLTB via official API by game name — more comprehensive than appid lookup."""
    try:
        headers = {
            'User-Agent': 'Steam Backlog App',
            'Content-Type': 'application/json'
        }
        payload = {
            'searchType': 'games',
            'searchTerms': [game_name],
            'size': 20,
            'searchPage': 1,
            'searchOptions': {
                'games': {'userId': 0, 'platform': '', 'sortCategory': 'popular', 'rangeCategory': 'main', 'rangeTime': {'min': 0, 'max': 0}, 'gameplay': {'perspective': '', 'flow': '', 'genre': ''}, 'modifier': ''},
                'users': {'sortCategory': 'postcount'},
                'lists': {'sortCategory': 'follows'},
                'reviews': {'sortCategory': 'helpfulness'}
            }
        }

        response = requests.post(
            'https://www.howlongtobeat.com/api/search',
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                # Find best match based on name similarity
                for game in data['data']:
                    # Prioritize exact matches or very close matches
                    game_title = game.get('game_name', '').lower()
                    search_term = game_name.lower()
                    if search_term in game_title or game_title in search_term:
                        main_time = game.get('comp_main')
                        if main_time and main_time > 0:
                            return {'mainStory': main_time}
                # If no close match, try first result
                first = data['data'][0]
                main_time = first.get('comp_main')
                if main_time and main_time > 0:
                    return {'mainStory': main_time}
        return None
    except Exception as e:
        print(f"  [HLTB API ERROR] {e}")
        return None

def run_hltb_sync():
    global sync_status
    sync_status = {"running": True, "updated": 0, "total": 0, "processed": 0}
    print("--- Starting HLTB Sync ---")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT appid, name FROM games WHERE hltb_hours IS NULL')
    games_to_scan = cur.fetchall()
    cur.close()
    conn.close()

    sync_status["total"] = len(games_to_scan)
    print(f"Found {len(games_to_scan)} games to scan.")

    updated_count = 0

    for game in games_to_scan:
        appid = game['appid']
        name = game['name']
        print(f"Scanning: {name}...")

        try:
            data = search_hltb_by_name(name, appid)

            if data and data.get('mainStory') and data['mainStory'] > 0:
                hours = round(data['mainStory'], 1)
                _run_update('UPDATE games SET hltb_hours = %s WHERE appid = %s', (hours, appid))
                updated_count += 1
                sync_status["updated"] = updated_count
                print(f"  [SUCCESS] {name}: {hours}h")
            elif data:
                print(f"  [SKIP] No main story time for {name}")
            else:
                print(f"  [NOT FOUND] No HLTB data for {name}")

            sync_status["processed"] += 1
            time.sleep(0.3)

        except Exception as e:
            import traceback
            print(f"  [ERROR] Failed on {name}: {str(e)}")
            traceback.print_exc()
            sync_status["processed"] += 1

    sync_status["running"] = False
    print(f"--- Sync Complete. Updated {updated_count} games. ---")
    update_sync_time('hltb')

@app.route('/sync_hltb', methods=['POST'])
def sync_hltb():
    if sync_status.get("running"):
        return jsonify({"error": "Sync already in progress"}), 409
    thread = threading.Thread(target=run_hltb_sync, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Sync started"})

@app.route('/sync_status', methods=['GET'])
def get_sync_status():
    return jsonify(sync_status)

def fetch_steam_store(appid, filters='basic', retries=3):
    """Fetch from Steam store API with retry and exponential backoff."""
    for attempt in range(retries):
        try:
            response = requests.get(
                'https://store.steampowered.com/api/appdetails',
                params={'appids': appid, 'filters': filters},
                timeout=10
            )
            data = response.json()
            if data is None:
                raise ValueError("Null response from Steam store API")
            return data.get(str(appid), {})
        except Exception as e:
            wait = 1.5 * (2 ** attempt)  # 1.5s, 3s, 6s
            print(f"  [RETRY {attempt + 1}/{retries}] appid {appid}: {e} — waiting {wait}s")
            time.sleep(wait)
    return {}

def run_free_sync():
    global free_sync_status
    free_sync_status = {"running": True, "updated": 0, "total": 0, "processed": 0}
    print("--- Starting Free Game Sync ---")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT DISTINCT appid, name FROM games WHERE is_free = FALSE')
    games_to_scan = cur.fetchall()
    cur.close()
    conn.close()

    free_sync_status["total"] = len(games_to_scan)
    print(f"Found {len(games_to_scan)} games to check.")

    updated_count = 0

    for game in games_to_scan:
        appid = game['appid']
        try:
            app_data = fetch_steam_store(appid, filters='basic')
            if app_data.get('success') and app_data.get('data', {}).get('is_free'):
                _run_update('UPDATE games SET is_free = TRUE WHERE appid = %s', (appid,))
                updated_count += 1
                free_sync_status["updated"] = updated_count
                print(f"  [FREE] {game['name']}")
            free_sync_status["processed"] += 1
            time.sleep(0.6)
        except Exception as e:
            print(f"  [ERROR] {game['name']}: {str(e)}")
            free_sync_status["processed"] += 1

    free_sync_status["running"] = False
    print(f"--- Free Sync Complete. Found {updated_count} free games. ---")
    update_sync_time('free')

@app.route('/sync_free', methods=['POST'])
def sync_free():
    if free_sync_status.get("running"):
        return jsonify({"error": "Sync already in progress"}), 409
    thread = threading.Thread(target=run_free_sync, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Sync started"})

@app.route('/free_sync_status', methods=['GET'])
def get_free_sync_status():
    return jsonify(free_sync_status)

genre_sync_status = {"running": False, "updated": 0, "total": 0}

def run_genre_sync():
    global genre_sync_status
    genre_sync_status = {"running": True, "updated": 0, "total": 0, "processed": 0}
    print("--- Starting Genre Sync ---")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT DISTINCT appid, name FROM games WHERE genres IS NULL')
    games_to_scan = cur.fetchall()
    cur.close()
    conn.close()

    genre_sync_status["total"] = len(games_to_scan)
    print(f"Found {len(games_to_scan)} games to check.")

    updated_count = 0

    for game in games_to_scan:
        appid = game['appid']
        try:
            app_data = fetch_steam_store(appid, filters='genres')
            if app_data.get('success'):
                genre_list = app_data.get('data', {}).get('genres', [])
                genres = ','.join(g['description'] for g in genre_list) if genre_list else ''
                _run_update('UPDATE games SET genres = %s WHERE appid = %s', (genres, appid))
                updated_count += 1
                genre_sync_status["updated"] = updated_count
                print(f"  [OK] {game['name']}: {genres}")
            genre_sync_status["processed"] += 1
            time.sleep(0.6)
        except Exception as e:
            print(f"  [ERROR] {game['name']}: {str(e)}")
            genre_sync_status["processed"] += 1

    genre_sync_status["running"] = False
    print(f"--- Genre Sync Complete. Updated {updated_count} games. ---")
    update_sync_time('genre')

@app.route('/sync_genres', methods=['POST'])
def sync_genres():
    if genre_sync_status.get("running"):
        return jsonify({"error": "Sync already in progress"}), 409
    thread = threading.Thread(target=run_genre_sync, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Sync started"})

@app.route('/genre_sync_status', methods=['GET'])
def get_genre_sync_status():
    return jsonify(genre_sync_status)

@app.route('/sync_metadata', methods=['GET'])
def get_sync_metadata_endpoint():
    metadata = get_sync_metadata()
    return jsonify(metadata)

@app.route('/force_refresh', methods=['POST'])
def force_refresh():
    """Force refresh a user's game library from Steam, bypassing cache."""
    steam_id = session.get('steam_id')
    if not steam_id:
        return jsonify({"error": "Session expired"}), 401

    try:
        steam_games = get_steam_library(steam_id)
        save_games_to_db(steam_id, steam_games)
        update_sync_time('library')
        return jsonify({"success": True, "message": "Library refreshed from Steam"}), 200
    except PrivateProfileError:
        return jsonify({"error": "Profile is private"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Setting host to 0.0.0.0 makes it accessible on your local network
    # In production (Render), these settings are overridden by gunicorn via Procfile
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)