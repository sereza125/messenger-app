#!/usr/bin/env python3
"""Simple HTTP-based messenger that works with any tunnel"""
import http.server
import socketserver
import json
import sqlite3
import threading
import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

PORT = 9000
DB_FILE = 'simple_chat.db'

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sender TEXT,
                  recipient TEXT,
                  content TEXT,
                  timestamp TEXT)''')
    conn.commit()
    return conn

db = init_db()

# Store active users and their last poll time
active_users = {}
users_lock = threading.Lock()

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        super().__init__(*args, **kwargs)
    
    def translate_path(self, path):
        # Override to serve files from the correct directory
        path = os.path.normpath(urlparse(path).path)
        words = path.split('/')
        words = filter(None, words)
        path = self.base_path
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir):
                continue
            path = os.path.join(path, word)
        return path
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/api/messages':
            self.handle_get_messages()
        elif path == '/api/users':
            self.handle_get_users()
        elif path == '/api/poll':
            self.handle_poll()
        else:
            super().do_GET()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/api/send':
            self.handle_send()
        elif path == '/api/login':
            self.handle_login()
        else:
            self.send_error(404)
    
    def handle_login(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body)
        username = data.get('username', 'Anonymous')
        
        with users_lock:
            active_users[username] = time.time()
        
        self.send_json({'success': True, 'username': username})
    
    def handle_send(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body)
        
        sender = data.get('sender')
        recipient = data.get('recipient', 'all')
        content = data.get('content', '')
        
        c = db.cursor()
        timestamp = datetime.now().isoformat()
        c.execute("INSERT INTO messages (sender, recipient, content, timestamp) VALUES (?, ?, ?, ?)",
                  (sender, recipient, content, timestamp))
        db.commit()
        
        self.send_json({'success': True, 'timestamp': timestamp, 'id': c.lastrowid})
    
    def handle_get_messages(self):
        query = parse_qs(urlparse(self.path).query)
        user = query.get('user', [''])[0]
        since = query.get('since', ['0'])[0]
        
        c = db.cursor()
        c.execute("""SELECT id, sender, recipient, content, timestamp 
                     FROM messages 
                     WHERE (recipient='all' OR recipient=? OR sender=?)
                     AND timestamp > ?
                     ORDER BY timestamp ASC""",
                  (user, user, since))
        
        messages = [{
            'id': row[0],
            'sender': row[1],
            'recipient': row[2],
            'content': row[3],
            'timestamp': row[4]
        } for row in c.fetchall()]
        
        self.send_json({'messages': messages})
    
    def handle_get_users(self):
        with users_lock:
            now = time.time()
            # Remove inactive users (5 min timeout)
            inactive = [u for u, t in active_users.items() if now - t > 300]
            for u in inactive:
                del active_users[u]
            users = list(active_users.keys())
        
        self.send_json({'users': users})
    
    def handle_poll(self):
        query = parse_qs(urlparse(self.path).query)
        user = query.get('user', [''])[0]
        
        if user:
            with users_lock:
                active_users[user] = time.time()
        
        self.send_json({'status': 'ok'})
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

def main():
    server = ThreadedHTTPServer(("", PORT), Handler)
    print(f"="*60)
    print(f"Messenger running on http://localhost:{PORT}")
    print(f"="*60)
    print("For external access, use one of these tunnels:")
    print("1. ngrok: ngrok http {PORT}")
    print("2. cloudflared: cloudflared tunnel --url http://localhost:{PORT}")
    print("3. SSH: ssh -R 80:localhost:{PORT} serveo.net")
    print(f"="*60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.shutdown()

if __name__ == "__main__":
    main()
