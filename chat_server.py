#!/usr/bin/env python3
"""Stable messenger server - single file, no external deps"""
import http.server
import socketserver
import json
import os
import sys
import sqlite3
import threading
import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

PORT = 9000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'chat.db')

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS messages
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     sender TEXT, recipient TEXT, content TEXT, timestamp TEXT)''')
    conn.commit()
    return conn

db = init_db()
active_users = {}
users_lock = threading.Lock()

class ChatHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith('/api/'):
            self.handle_api_get(path, parsed)
        else:
            self.serve_file(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith('/api/'):
            self.handle_api_post(path)
        else:
            self.send_error(404)

    def serve_file(self, path):
        if path == '/' or path == '':
            path = '/simple.html'
        
        filepath = os.path.join(BASE_DIR, path.lstrip('/'))
        filepath = os.path.normpath(filepath)
        
        if not filepath.startswith(BASE_DIR):
            self.send_error(403)
            return
        
        if os.path.isfile(filepath):
            ext = os.path.splitext(filepath)[1]
            types = {'.html': 'text/html', '.js': 'application/javascript',
                     '.css': 'text/css', '.png': 'image/png', '.ico': 'image/x-icon'}
            ctype = types.get(ext, 'application/octet-stream')
            
            self.send_response(200)
            self.send_header('Content-Type', ctype + '; charset=utf-8')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404)

    def handle_api_get(self, path, parsed):
        query = parse_qs(parsed.query)
        
        if path == '/api/messages':
            user = query.get('user', [''])[0]
            since = query.get('since', ['1970-01-01'])[0]
            rows = db.execute(
                """SELECT id, sender, recipient, content, timestamp 
                   FROM messages 
                   WHERE (recipient='all' OR recipient=? OR sender=?) AND timestamp > ?
                   ORDER BY timestamp ASC""", (user, user, since)).fetchall()
            msgs = [{'id':r[0],'sender':r[1],'recipient':r[2],'content':r[3],'timestamp':r[4]} for r in rows]
            self.send_json({'messages': msgs})
        
        elif path == '/api/users':
            with users_lock:
                now = time.time()
                dead = [u for u,t in active_users.items() if now-t > 300]
                for u in dead: del active_users[u]
                self.send_json({'users': list(active_users.keys())})
        
        elif path == '/api/poll':
            user = query.get('user', [''])[0]
            if user:
                with users_lock:
                    active_users[user] = time.time()
            self.send_json({'status': 'ok'})
        
        else:
            self.send_error(404)

    def handle_api_post(self, path):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else '{}'
        data = json.loads(body)
        
        if path == '/api/login':
            username = data.get('username', 'Anon')
            with users_lock:
                active_users[username] = time.time()
            self.send_json({'success': True, 'username': username})
        
        elif path == '/api/send':
            ts = datetime.now().isoformat()
            c = db.execute("INSERT INTO messages (sender,recipient,content,timestamp) VALUES (?,?,?,?)",
                           (data.get('sender'), data.get('recipient','all'), data.get('content',''), ts))
            db.commit()
            self.send_json({'success': True, 'timestamp': ts, 'id': c.lastrowid})
        
        else:
            self.send_error(404)

    def send_json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # silent


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    server = ThreadedServer(('0.0.0.0', port), ChatHandler)
    print(f"Messenger running on http://localhost:{port}")
    print(f"Open http://localhost:{port}/simple.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
        server.shutdown()
