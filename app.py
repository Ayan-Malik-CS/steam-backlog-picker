from flask import Flask, render_template, request, jsonify, session, flash, redirect, url_for
from steam_api import get_steam_library, resolve_vanity_url
from database import get_active_games, save_games_to_db, get_db_connection, get_ignored_games, is_cache_stale, init_db
from howlongtobeatpy import HowLongToBeat
import time
import threading
import requests

app = Flask(__name__)
app.secret_key = 'change-this-to-a-random-secret-in-production'
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
        except ConnectionError as e:
            flash(str(e))
            return redirect(url_for('index'))

    games = get_active_games(steam_id)

    # Inside show_backlog function:
    ignored_games = get_ignored_games(steam_id)
    return render_template('dashboard.html', games=games, ignored_games=ignored_games)

@app.route('/ignore/<int:appid>', methods=['POST'])
def ignore_game(appid):
    steam_id = session.get('steam_id')
    if not steam_id:
        return jsonify({"error": "Session expired"}), 401
    conn = get_db_connection()
    conn.execute('UPDATE games SET is_ignored = 1 WHERE appid = ? AND steam_id = ?', (appid, steam_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True}), 200

@app.route('/unignore/<int:appid>', methods=['POST'])
def unignore_game(appid):
    steam_id = session.get('steam_id')
    if not steam_id:
        return jsonify({"error": "Session expired"}), 401
    conn = get_db_connection()
    conn.execute('UPDATE games SET is_ignored = 0 WHERE appid = ? AND steam_id = ?', (appid, steam_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True}), 200

sync_status = {"running": False, "updated": 0, "total": 0}

def run_hltb_sync():
    global sync_status
    sync_status = {"running": True, "updated": 0, "total": 0}
    print("--- Starting HLTB Sync ---")

    conn = get_db_connection()
    games_to_scan = conn.execute('SELECT appid, name FROM games WHERE hltb_hours IS NULL').fetchall()
    conn.close()

    sync_status["total"] = len(games_to_scan)
    print(f"Found {len(games_to_scan)} games to scan.")

    hltb = HowLongToBeat()
    updated_count = 0

    for game in games_to_scan:
        name = game['name']
        print(f"Scanning: {name}...")

        try:
            results = hltb.search(name, similarity_case_sensitive=False)

            if results and len(results) > 0:
                best_match = max(results, key=lambda element: element.similarity)

                hours = getattr(best_match, 'main_story', -1)
                if hours <= 0:
                    hours = getattr(best_match, 'gameplay_main', -1)

                if hours > 0:
                    conn = get_db_connection()
                    conn.execute('UPDATE games SET hltb_hours = ? WHERE appid = ?', (hours, game['appid']))
                    conn.commit()
                    conn.close()
                    updated_count += 1
                    sync_status["updated"] = updated_count
                    print(f"  [SUCCESS] Found {hours} hours for {name}")
                else:
                    print(f"  [SKIP] No time data found for {name}")
            else:
                print(f"  [NOT FOUND] No results on HLTB for {name}")

            time.sleep(0.5)

        except Exception as e:
            print(f"  [ERROR] Failed on {name}: {str(e)}")

    sync_status["running"] = False
    print(f"--- Sync Complete. Updated {updated_count} games. ---")

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

free_sync_status = {"running": False, "updated": 0, "total": 0}

def run_free_sync():
    global free_sync_status
    free_sync_status = {"running": True, "updated": 0, "total": 0}
    print("--- Starting Free Game Sync ---")

    conn = get_db_connection()
    games_to_scan = conn.execute('SELECT DISTINCT appid, name FROM games WHERE is_free = 0').fetchall()
    conn.close()

    free_sync_status["total"] = len(games_to_scan)
    print(f"Found {len(games_to_scan)} games to check.")

    updated_count = 0

    for game in games_to_scan:
        appid = game['appid']
        try:
            response = requests.get(
                'https://store.steampowered.com/api/appdetails',
                params={'appids': appid, 'filters': 'basic'},
                timeout=10
            )
            data = response.json()
            app_data = data.get(str(appid), {})

            if app_data.get('success') and app_data.get('data', {}).get('is_free'):
                conn = get_db_connection()
                conn.execute('UPDATE games SET is_free = 1 WHERE appid = ?', (appid,))
                conn.commit()
                conn.close()
                updated_count += 1
                free_sync_status["updated"] = updated_count
                print(f"  [FREE] {game['name']}")

            time.sleep(0.3)

        except Exception as e:
            print(f"  [ERROR] {game['name']}: {str(e)}")

    free_sync_status["running"] = False
    print(f"--- Free Sync Complete. Found {updated_count} free games. ---")

    free_sync_status["running"] = False
    print(f"--- Free Sync Complete. Found {updated_count} free games. ---")

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

if __name__ == '__main__':
    # Setting host to 0.0.0.0 makes it accessible on your local network
    app.run(debug=True, host='0.0.0.0', port=5000)