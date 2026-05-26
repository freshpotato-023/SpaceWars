import os
import sqlite3
import hashlib
from flask import Flask, request, jsonify


DB_PATH = os.path.join(os.path.dirname(__file__), "game_records.db")

app = Flask(__name__)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn):
    # Try a couple of likely schemas.
    # If table exists, we won't overwrite.
    cur = conn.cursor()
    # users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            highscore INTEGER DEFAULT 0,
            gamesplayed INTEGER DEFAULT 0,
            lastscore INTEGER,
            lastwave INTEGER
        )
        """
    )
    conn.commit()


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True)
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    if not username or not password:
        return jsonify({'ok': False, 'error': 'Missing username/password'}), 400

    conn = get_conn()
    try:
        ensure_schema(conn)
        cur = conn.cursor()
        # Hash password so we don't store plaintext
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

        # Register if missing
        cur.execute("SELECT username FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO users(username, password, highscore, gamesplayed, lastscore, lastwave) VALUES(?,?,?,?,?,?)",
                (username, password_hash, 0, 0, None, None),
            )
            conn.commit()

        # Validate password
        cur.execute(
            "SELECT password, highscore, gamesplayed, lastscore, lastwave FROM users WHERE username=?",
            (username,),
        )
        u = cur.fetchone()
        if u is None:
            return jsonify({'ok': False, 'error': 'User not found'}), 404

        stored_hash = u['password']
        if stored_hash and stored_hash != password_hash:
            return jsonify({'ok': False, 'error': 'Invalid password'}), 401


        return jsonify({
            'ok': True,
            'username': username,
            'highScore': u['highscore'] or 0,
            'gamesPlayed': u['gamesplayed'] or 0,
            'lastScore': u['lastscore'],
            'lastWave': u['lastwave']
        })
    finally:
        conn.close()


@app.route('/api/save_score', methods=['POST'])
def api_save_score():
    data = request.get_json(force=True)
    username = (data.get('username') or '').strip()
    score = int(data.get('score') or 0)
    wave = int(data.get('wave') or 1)

    if not username:
        return jsonify({'ok': False, 'error': 'Missing username'}), 400

    conn = get_conn()
    try:
        ensure_schema(conn)
        cur = conn.cursor()

        cur.execute("SELECT highscore, gamesplayed FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        if row is None:
            # Auto-register
            cur.execute(
                "INSERT INTO users(username, password, highscore, gamesplayed, lastscore, lastwave) VALUES(?,?,?,?,?,?)",
                (username, 'set-by-client', 0, 0, None, None),
            )

        cur.execute(
            "SELECT highscore, gamesplayed FROM users WHERE username=?",
            (username,),
        )
        row = cur.fetchone()
        prev_high = int(row['highscore'] or 0)
        games = int(row['gamesplayed'] or 0)

        new_high = prev_high
        if score > prev_high:
            new_high = score

        games += 1

        cur.execute(
            "UPDATE users SET highscore=?, gamesplayed=?, lastscore=?, lastwave=? WHERE username=?",
            (new_high, games, score, wave, username),
        )
        conn.commit()

        return jsonify({'ok': True, 'highScore': new_high, 'gamesPlayed': games})
    finally:
        conn.close()


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'ok': True, 'db': DB_PATH})


if __name__ == '__main__':
    # Use a fixed port so the HTML can call it.
    app.run(host='127.0.0.1', port=5000, debug=False)

