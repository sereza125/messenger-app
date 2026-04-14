#!/usr/bin/env python3
"""Stable Flask-based messenger"""
from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3
import time
import threading
import os
from datetime import datetime

app = Flask(__name__, template_folder='.', static_folder='.')

# Database setup
DB_FILE = os.path.join(os.path.dirname(__file__), 'chat.db')

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sender TEXT, recipient TEXT, content TEXT, timestamp TEXT)''')
    conn.commit()
    return conn

db = init_db()
active_users = {}
users_lock = threading.Lock()

@app.route('/')
def index():
    return send_from_directory('.', 'simple.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', 'Anonymous')
    with users_lock:
        active_users[username] = time.time()
    return jsonify({'success': True, 'username': username})

@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.json
    c = db.cursor()
    timestamp = datetime.now().isoformat()
    c.execute("INSERT INTO messages (sender, recipient, content, timestamp) VALUES (?, ?, ?, ?)",
              (data.get('sender'), data.get('recipient', 'all'), data.get('content'), timestamp))
    db.commit()
    return jsonify({'success': True, 'timestamp': timestamp, 'id': c.lastrowid})

@app.route('/api/messages')
def get_messages():
    user = request.args.get('user', '')
    since = request.args.get('since', '1970-01-01')
    c = db.cursor()
    c.execute("""SELECT id, sender, recipient, content, timestamp 
                 FROM messages 
                 WHERE (recipient='all' OR recipient=? OR sender=?) AND timestamp > ?
                 ORDER BY timestamp ASC""", (user, user, since))
    messages = [{'id': r[0], 'sender': r[1], 'recipient': r[2], 'content': r[3], 'timestamp': r[4]} for r in c.fetchall()]
    return jsonify({'messages': messages})

@app.route('/api/users')
def get_users():
    with users_lock:
        now = time.time()
        inactive = [u for u, t in active_users.items() if now - t > 300]
        for u in inactive:
            del active_users[u]
        users = list(active_users.keys())
    return jsonify({'users': users})

@app.route('/api/poll')
def poll():
    user = request.args.get('user', '')
    if user:
        with users_lock:
            active_users[user] = time.time()
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    print("="*60)
    print("Flask Messenger running on http://localhost:8040")
    print("="*60)
    app.run(host='0.0.0.0', port=8040, threaded=True)
