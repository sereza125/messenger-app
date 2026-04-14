import asyncio
import websockets
import json
import os
import sqlite3
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
from datetime import datetime

# Database setup
def init_db():
    conn = sqlite3.connect('chat.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sender TEXT,
                  recipient TEXT,
                  content TEXT,
                  timestamp TEXT,
                  is_read INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  joined_at TEXT)''')
    conn.commit()
    return conn

db_conn = init_db()

# Active connections: {username: websocket}
clients = {}
clients_lock = asyncio.Lock()

# Message storage for broadcast
message_history = []
MAX_HISTORY = 100

async def save_message(sender, recipient, content):
    """Save message to database"""
    c = db_conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute("INSERT INTO messages (sender, recipient, content, timestamp) VALUES (?, ?, ?, ?)",
              (sender, recipient, content, timestamp))
    db_conn.commit()
    return timestamp

async def get_chat_history(user1, user2, limit=50):
    """Get chat history between two users"""
    c = db_conn.cursor()
    c.execute("""SELECT sender, recipient, content, timestamp, is_read 
                 FROM messages 
                 WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)
                 ORDER BY timestamp DESC LIMIT ?""",
              (user1, user2, user2, user1, limit))
    return c.fetchall()

async def get_user_chats(username):
    """Get list of chats for user"""
    c = db_conn.cursor()
    c.execute("""SELECT DISTINCT 
                 CASE WHEN sender=? THEN recipient ELSE sender END as chat_user,
                 MAX(timestamp) as last_time
                 FROM messages 
                 WHERE sender=? OR recipient=?
                 GROUP BY chat_user
                 ORDER BY last_time DESC""",
              (username, username, username))
    return c.fetchall()

async def broadcast(message, exclude=None):
    """Broadcast to all connected clients"""
    disconnected = []
    async with clients_lock:
        for username, websocket in clients.items():
            if username != exclude:
                try:
                    await websocket.send(json.dumps(message))
                except:
                    disconnected.append(username)
        
        for username in disconnected:
            if username in clients:
                del clients[clients]

async def send_to_user(username, message):
    """Send message to specific user"""
    async with clients_lock:
        if username in clients:
            try:
                await clients[username].send(json.dumps(message))
                return True
            except:
                return False
    return False

async def handler(websocket):
    """Handle WebSocket connection"""
    username = None
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get('type')
                
                if msg_type == 'login':
                    username = data.get('username', 'Anonymous')
                    
                    async with clients_lock:
                        # Remove old connection if exists
                        if username in clients:
                            try:
                                await clients[username].close()
                            except:
                                pass
                        clients[username] = websocket
                    
                    # Save user to DB
                    c = db_conn.cursor()
                    c.execute("INSERT OR IGNORE INTO users (username, joined_at) VALUES (?, ?)",
                              (username, datetime.now().isoformat()))
                    db_conn.commit()
                    
                    # Send user list
                    async with clients_lock:
                        user_list = list(clients.keys())
                    
                    await websocket.send(json.dumps({
                        'type': 'login_success',
                        'username': username,
                        'users_online': user_list
                    }))
                    
                    # Notify others
                    await broadcast({
                        'type': 'user_joined',
                        'username': username,
                        'users_online': user_list
                    }, exclude=username)
                    
                    print(f"[+] {username} logged in. Online: {len(clients)}")
                    
                elif msg_type == 'get_chat_list':
                    if username:
                        chats = await get_user_chats(username)
                        await websocket.send(json.dumps({
                            'type': 'chat_list',
                            'chats': [{'username': c[0], 'last_time': c[1]} for c in chats]
                        }))
                        
                elif msg_type == 'get_history':
                    if username:
                        chat_with = data.get('with_user', 'all')
                        if chat_with == 'all':
                            # Global chat - last 50 messages
                            c = db_conn.cursor()
                            c.execute("""SELECT sender, recipient, content, timestamp, is_read 
                                         FROM messages WHERE recipient='all'
                                         ORDER BY timestamp DESC LIMIT 50""")
                            history = c.fetchall()
                        else:
                            history = await get_chat_history(username, chat_with)
                        
                        await websocket.send(json.dumps({
                            'type': 'chat_history',
                            'with_user': chat_with,
                            'messages': [{
                                'sender': h[0],
                                'recipient': h[1],
                                'content': h[2],
                                'timestamp': h[3],
                                'is_read': bool(h[4])
                            } for h in reversed(history)]
                        }))
                        
                elif msg_type == 'message':
                    if username:
                        content = data.get('content', '')
                        recipient = data.get('recipient', 'all')
                        
                        # Save to DB
                        timestamp = await save_message(username, recipient, content)
                        
                        msg_data = {
                            'type': 'new_message',
                            'sender': username,
                            'recipient': recipient,
                            'content': content,
                            'timestamp': timestamp,
                            'message_id': data.get('message_id')
                        }
                        
                        if recipient == 'all':
                            # Broadcast to all
                            await broadcast(msg_data, exclude=username)
                        else:
                            # Send to specific user
                            await send_to_user(recipient, msg_data)
                            # Send confirmation to sender
                            await websocket.send(json.dumps({
                                'type': 'message_sent',
                                'recipient': recipient,
                                'message_id': data.get('message_id'),
                                'timestamp': timestamp
                            }))
                            
                elif msg_type == 'typing':
                    if username:
                        recipient = data.get('recipient', 'all')
                        if recipient != 'all':
                            await send_to_user(recipient, {
                                'type': 'typing',
                                'username': username
                            })
                            
                elif msg_type == 'mark_read':
                    if username:
                        sender = data.get('sender')
                        c = db_conn.cursor()
                        c.execute("UPDATE messages SET is_read=1 WHERE sender=? AND recipient=? AND is_read=0",
                                  (sender, username))
                        db_conn.commit()
                        
                        # Notify sender
                        await send_to_user(sender, {
                            'type': 'messages_read',
                            'by_user': username
                        })
                        
            except json.JSONDecodeError:
                print(f"[!] Invalid JSON from {username}")
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if username:
            async with clients_lock:
                if username in clients and clients[username] == websocket:
                    del clients[username]
            
            await broadcast({
                'type': 'user_left',
                'username': username,
                'users_online': list(clients.keys())
            })
            
            print(f"[-] {username} disconnected. Online: {len(clients)}")

class CustomHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    
    def log_message(self, format, *args):
        pass

def start_http_server():
    server = HTTPServer(('0.0.0.0', 8011), CustomHandler)
    print(f"[HTTP] Server running at http://localhost:8011")
    server.serve_forever()

async def main():
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    print("[WebSocket] Starting on ws://localhost:8771")
    async with websockets.serve(handler, "0.0.0.0", 8771):
        print("=" * 50)
        print("Telegram-like Messenger ready!")
        print("Open http://localhost:8011/telegram.html in browser")
        print("Press Ctrl+C to stop")
        print("=" * 50)
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
        db_conn.close()
