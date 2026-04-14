from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import Dict, List
import json

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
    
    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)
    
    async def broadcast(self, message: str, exclude: str = None):
        for client_id, connection in self.active_connections.items():
            if client_id != exclude:
                await connection.send_text(message)

manager = ConnectionManager()

@app.get("/")
async def get():
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Python Messenger</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; justify-content: center; align-items: center; }
        .chat-container { width: 400px; height: 600px; background: white; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); display: flex; flex-direction: column; overflow: hidden; }
        .chat-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; color: white; text-align: center; }
        .chat-messages { flex: 1; overflow-y: auto; padding: 20px; background: #f5f5f5; }
        .message { margin-bottom: 15px; padding: 12px 16px; border-radius: 18px; max-width: 80%; word-wrap: break-word; }
        .message.sent { background: #667eea; color: white; margin-left: auto; border-bottom-right-radius: 4px; }
        .message.received { background: white; color: #333; border-bottom-left-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .message .username { font-size: 12px; font-weight: bold; margin-bottom: 4px; opacity: 0.8; }
        .message .time { font-size: 10px; opacity: 0.6; margin-top: 4px; }
        .chat-input { padding: 20px; background: white; border-top: 1px solid #eee; display: flex; gap: 10px; }
        .chat-input input { flex: 1; padding: 12px 16px; border: 2px solid #eee; border-radius: 25px; outline: none; font-size: 14px; }
        .chat-input input:focus { border-color: #667eea; }
        .chat-input button { padding: 12px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 25px; cursor: pointer; font-size: 14px; font-weight: bold; }
        .chat-input button:hover { transform: scale(1.05); }
        .login-container { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; justify-content: center; align-items: center; z-index: 1000; }
        .login-box { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; }
        .login-box h2 { margin-bottom: 20px; color: #333; }
        .login-box input { width: 100%; padding: 15px; margin-bottom: 20px; border: 2px solid #eee; border-radius: 10px; font-size: 16px; outline: none; }
        .login-box input:focus { border-color: #667eea; }
        .login-box button { width: 100%; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 10px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .system-message { text-align: center; color: #666; font-size: 12px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="login-container" id="loginContainer">
        <div class="login-box">
            <h2>Войти в мессенджер</h2>
            <input type="text" id="usernameInput" placeholder="Введите имя..." maxlength="20">
            <button onclick="login()">Войти</button>
        </div>
    </div>

    <div class="chat-container" id="chatContainer" style="display: none;">
        <div class="chat-header">
            <h2>💬 Python Messenger</h2>
            <small id="userDisplay"></small>
        </div>
        <div class="chat-messages" id="messages"></div>
        <div class="chat-input">
            <input type="text" id="messageInput" placeholder="Введите сообщение..." maxlength="500">
            <button onclick="sendMessage()">Отправить</button>
        </div>
    </div>

    <script>
        let ws;
        let username;
        let clientId;

        function login() {
            username = document.getElementById('usernameInput').value.trim();
            if (!username) return;
            
            clientId = Date.now().toString();
            document.getElementById('loginContainer').style.display = 'none';
            document.getElementById('chatContainer').style.display = 'flex';
            document.getElementById('userDisplay').textContent = 'Вы: ' + username;
            
            connectWebSocket();
        }

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/${clientId}`);
            
            ws.onopen = () => {
                console.log('Connected to server');
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                displayMessage(data);
            };
            
            ws.onclose = () => {
                console.log('Disconnected from server');
                addSystemMessage('Соединение разорвано. Переподключаемся...');
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }

        function displayMessage(data) {
            const messagesDiv = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            
            if (data.type === 'system') {
                messageDiv.className = 'system-message';
                messageDiv.textContent = data.message;
            } else {
                const isSent = data.client_id === clientId;
                messageDiv.className = `message ${isSent ? 'sent' : 'received'}`;
                
                const time = new Date(data.timestamp).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
                
                messageDiv.innerHTML = `
                    ${!isSent ? `<div class="username">${data.username}</div>` : ''}
                    <div>${escapeHtml(data.message)}</div>
                    <div class="time">${time}</div>
                `;
            }
            
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function addSystemMessage(text) {
            const messagesDiv = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'system-message';
            messageDiv.textContent = text;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message || !ws || ws.readyState !== WebSocket.OPEN) return;
            
            const data = {
                type: 'message',
                username: username,
                message: message,
                client_id: clientId,
                timestamp: new Date().toISOString()
            };
            
            ws.send(JSON.stringify(data));
            input.value = '';
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        document.getElementById('usernameInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') login();
        });

        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    
    await manager.broadcast(json.dumps({
        "type": "system",
        "message": f"Пользователь {client_id[:8]}... подключился"
    }), exclude=client_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            await manager.broadcast(json.dumps(message_data))
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(json.dumps({
            "type": "system",
            "message": f"Пользователь {client_id[:8]}... отключился"
        }))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
