import asyncio
import websockets
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

# Хранение подключенных клиентов
clients = {}

async def broadcast(message, sender=None):
    """Отправить сообщение всем клиентам"""
    disconnected = []
    for client_id, websocket in clients.items():
        if client_id != sender:
            try:
                await websocket.send(message)
            except:
                disconnected.append(client_id)
    
    # Удалить отключившихся клиентов
    for client_id in disconnected:
        if client_id in clients:
            del clients[client_id]

async def handler(websocket):
    """Обработчик WebSocket соединений"""
    client_id = id(websocket)
    username = None
    
    # Добавляем клиента
    clients[client_id] = websocket
    print(f"[+] Client {client_id} connected. Total: {len(clients)}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get('type')
                
                if msg_type == 'login':
                    username = data.get('username', 'Anonymous')
                    await broadcast(json.dumps({
                        'type': 'system',
                        'message': f'{username} присоединился к чату'
                    }), sender=client_id)
                    
                elif msg_type == 'message' and username:
                    await broadcast(json.dumps({
                        'type': 'message',
                        'username': username,
                        'message': data.get('message', ''),
                        'timestamp': data.get('timestamp', '')
                    }))
                    
            except json.JSONDecodeError:
                print(f"[!] Invalid message format from {client_id}")
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Удаляем клиента при отключении
        if client_id in clients:
            del clients[client_id]
        
        if username:
            await broadcast(json.dumps({
                'type': 'system',
                'message': f'{username} покинул чат'
            }))
        
        print(f"[-] Client {client_id} disconnected. Total: {len(clients)}")

class CustomHandler(SimpleHTTPRequestHandler):
    """HTTP обработчик для раздачи статических файлов"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    
    def log_message(self, format, *args):
        # Отключаем логирование HTTP запросов
        pass

def start_http_server():
    """Запуск HTTP сервера"""
    server = HTTPServer(('0.0.0.0', 8002), CustomHandler)
    print(f"[HTTP] Server running at http://localhost:8002")
    server.serve_forever()

async def main():
    # Запуск HTTP сервера в отдельном потоке
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Запуск WebSocket сервера
    print("[WebSocket] Starting on ws://localhost:8767")
    async with websockets.serve(handler, "0.0.0.0", 8767):
        print("=" * 50)
        print("Messenger is ready!")
        print("Open http://localhost:8002 in browser")
        print("Press Ctrl+C to stop")
        print("=" * 50)
        await asyncio.Future()  # Работать бесконечно

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
