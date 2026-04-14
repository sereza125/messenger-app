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
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

PORT = 9000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'chat.db')

# SMTP Configuration (use Gmail or any SMTP server)
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_EMAIL = ''  # Set your email
SMTP_PASSWORD = ''  # Set your app password

def send_otp_email(email, otp):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print(f"SMTP not configured. OTP for {email}: {otp}")
        return False
    
    try:
        msg = MIMEText(f'Ваш код подтверждения: {otp}\n\nКод действителен 10 минут.')
        msg['Subject'] = 'Код подтверждения Messenger'
        msg['From'] = SMTP_EMAIL
        msg['To'] = email
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"OTP sent to {email}: {otp}")
        return True
    except Exception as e:
        print(f"SMTP error: {e}")
        print(f"DEV MODE: OTP for {email}: {otp}")
        return False

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS messages
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     sender TEXT, recipient TEXT, content TEXT, timestamp TEXT,
                     read INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS users
                    (username TEXT PRIMARY KEY, avatar_color TEXT, online INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS otp_codes
                    (email TEXT PRIMARY KEY, otp TEXT, expires_at TEXT, verified INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS webrtc_signals
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     sender TEXT, recipient TEXT, signal_type TEXT, signal_data TEXT, timestamp TEXT)''')
    conn.commit()
    return conn

db = init_db()
active_users = {}
users_lock = threading.Lock()

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def generate_captcha():
    """Generate math captcha question and answer"""
    operations = ['+', '-', '*']
    op = random.choice(operations)
    
    if op == '+':
        a = random.randint(1, 50)
        b = random.randint(1, 50)
        answer = a + b
    elif op == '-':
        a = random.randint(10, 50)
        b = random.randint(1, a)
        answer = a - b
    else:  # *
        a = random.randint(2, 10)
        b = random.randint(2, 10)
        answer = a * b
    
    question = f"{a} {op} {b} = ?"
    return question, str(answer)

captcha_challenges = {}
captcha_attempts = {}  # Track failed attempts per IP/email

def create_otp(email):
    otp = generate_otp()
    expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
    db.execute("INSERT OR REPLACE INTO otp_codes (email, otp, expires_at, verified) VALUES (?, ?, ?, 0)",
               (email, otp, expires_at))
    db.commit()
    
    # Send email via SMTP
    email_sent = send_otp_email(email, otp)
    
    return otp, email_sent

def verify_otp(email, otp):
    row = db.execute("SELECT otp, expires_at, verified FROM otp_codes WHERE email=?", (email,)).fetchone()
    if not row:
        return False, "OTP not found"
    
    stored_otp, expires_at, verified = row
    if verified:
        return False, "Already verified"
    
    if datetime.now() > datetime.fromisoformat(expires_at):
        return False, "OTP expired"
    
    if stored_otp != otp:
        return False, "Invalid OTP"
    
    db.execute("UPDATE otp_codes SET verified=1 WHERE email=?", (email,))
    db.commit()
    return True, "Verified"

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
                """SELECT id, sender, recipient, content, timestamp, read
                   FROM messages 
                   WHERE (recipient='all' OR recipient=? OR sender=?) AND timestamp > ?
                   ORDER BY timestamp ASC""", (user, user, since)).fetchall()
            msgs = [{'id':r[0],'sender':r[1],'recipient':r[2],'content':r[3],'timestamp':r[4],'read':r[5]} for r in rows]
            self.send_json({'messages': msgs})
        
        elif path == '/api/unread':
            user = query.get('user', [''])[0]
            rows = db.execute(
                """SELECT COUNT(*) FROM messages 
                   WHERE recipient=? AND read=0""", (user,)).fetchone()
            unread_count = rows[0] if rows else 0
            self.send_json({'unread': unread_count})
        
        elif path == '/api/captcha':
            import uuid
            captcha_id = str(uuid.uuid4())
            question, answer = generate_captcha()
            captcha_challenges[captcha_id] = answer
            self.send_json({'captcha_id': captcha_id, 'question': question})
        
        elif path == '/api/users':
            with users_lock:
                now = time.time()
                dead = [u for u,t in active_users.items() if now-t > 300]
                for u in dead: 
                    del active_users[u]
                    db.execute("UPDATE users SET online=0 WHERE username=?", (u,))
                    db.commit()
                
                users = []
                for username in active_users.keys():
                    user_row = db.execute("SELECT avatar_color FROM users WHERE username=?", (username,)).fetchone()
                    color = user_row[0] if user_row else None
                    users.append({'username': username, 'avatar_color': color, 'online': True})
                
                self.send_json({'users': users})
        
        elif path == '/api/user-info':
            username = query.get('username', [''])[0]
            user_row = db.execute("SELECT avatar_color, online FROM users WHERE username=?", (username,)).fetchone()
            if user_row:
                self.send_json({'username': username, 'avatar_color': user_row[0], 'online': user_row[1]})
            else:
                self.send_json({'username': username, 'avatar_color': None, 'online': False})
        
        elif path == '/api/poll':
            user = query.get('user', [''])[0]
            if user:
                with users_lock:
                    active_users[user] = time.time()
                    db.execute("INSERT OR IGNORE INTO users (username, online) VALUES (?, 1)", (user,))
                    db.execute("UPDATE users SET online=1 WHERE username=?", (user,))
                    db.commit()
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
        
        elif path == '/api/mark-read':
            user = data.get('user', '')
            if user:
                db.execute("UPDATE messages SET read=1 WHERE recipient=? AND read=0", (user,))
                db.commit()
                self.send_json({'success': True})
            else:
                self.send_error(400)
        
        elif path == '/api/captcha':
            import uuid
            captcha_id = str(uuid.uuid4())
            question, answer = generate_captcha()
            captcha_challenges[captcha_id] = answer
            self.send_json({'captcha_id': captcha_id, 'question': question})
        
        elif path == '/api/auth/create-user-with-otp':
            email = data.get('email', '').lower().strip()
            captcha_id = data.get('captcha_id', '')
            captcha_answer = data.get('captcha_answer', '').strip()
            
            if not email:
                self.send_error(400)
                return
            
            # Check attempt limits
            client_ip = self.client_address[0]
            if client_ip in captcha_attempts and captcha_attempts[client_ip] >= 5:
                self.send_json({'success': False, 'error': 'Слишком много попыток. Подождите 5 минут.'})
                return
            
            # Verify captcha
            if captcha_id and captcha_id in captcha_challenges:
                if captcha_challenges[captcha_id] != captcha_answer:
                    captcha_attempts[client_ip] = captcha_attempts.get(client_ip, 0) + 1
                    remaining = 5 - captcha_attempts[client_ip]
                    self.send_json({'success': False, 'error': f'Неверный ответ. Осталось попыток: {remaining}'})
                    return
                del captcha_challenges[captcha_id]
                if client_ip in captcha_attempts:
                    del captcha_attempts[client_ip]
            else:
                self.send_json({'success': False, 'error': 'Капча обязательна. Обновите страницу.'})
                return
            
            # Validate email format
            if '@' not in email or '.' not in email.split('@')[1]:
                self.send_json({'success': False, 'error': 'Некорректный email'})
                return
            
            otp, email_sent = create_otp(email)
            
            if email_sent:
                message = 'Код отправлен на email'
                show_otp = False
            else:
                message = 'SMTP не настроен'
                show_otp = True
            
            self.send_json({'success': True, 'message': message, 'otp': otp if show_otp else None, 'userId': email, 'email_sent': email_sent})
        
        elif path == '/api/auth/verify-otp':
            email = data.get('userId', '')
            otp = data.get('otp', '')
            if not email or not otp:
                self.send_error(400)
                return
            
            success, message = verify_otp(email, otp)
            if success:
                # Create user account
                username = email.split('@')[0]
                colors = [
                    'linear-gradient(145deg, #ff7b7b, #c94b4b)',
                    'linear-gradient(145deg, #6bcb77, #2e8b57)',
                    'linear-gradient(145deg, #4dabf7, #1a73e8)',
                    'linear-gradient(145deg, #ffd43b, #fab005)',
                    'linear-gradient(145deg, #da77f2, #be4bdb)',
                    'linear-gradient(145deg, #ff8787, #e03131)'
                ]
                hash_val = sum(ord(c) for c in username)
                color = colors[hash_val % len(colors)]
                db.execute("INSERT OR IGNORE INTO users (username, avatar_color, online) VALUES (?, ?, 1)",
                          (username, color))
                db.commit()
                self.send_json({'success': True, 'message': 'Verified', 'userId': username, 'email': email})
            else:
                self.send_json({'success': False, 'error': message})
        
        elif path == '/api/webrtc':
            action = data.get('action', '')
            if action == 'send_signal':
                sender = data.get('sender', '')
                recipient = data.get('recipient', '')
                signal_type = data.get('signal_type', '')
                signal_data = data.get('signal_data', '')
                ts = datetime.now().isoformat()
                db.execute("INSERT INTO webrtc_signals (sender,recipient,signal_type,signal_data,timestamp) VALUES (?,?,?,?,?)",
                          (sender, recipient, signal_type, json.dumps(signal_data), ts))
                db.commit()
                self.send_json({'success': True})
            elif action == 'get_signals':
                user = data.get('user', '')
                since = data.get('since', '1970-01-01')
                rows = db.execute("SELECT sender, signal_type, signal_data, timestamp FROM webrtc_signals WHERE recipient=? AND timestamp > ? ORDER BY timestamp ASC",
                                 (user, since)).fetchall()
                signals = [{'sender':r[0], 'signal_type':r[1], 'signal_data':json.loads(r[2]), 'timestamp':r[3]} for r in rows]
                self.send_json({'signals': signals})
            elif action == 'cleanup_signals':
                user = data.get('user', '')
                db.execute("DELETE FROM webrtc_signals WHERE recipient=?", (user,))
                db.commit()
                self.send_json({'success': True})
            else:
                self.send_error(400)
        
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
