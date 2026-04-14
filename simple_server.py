import socket
import threading
import json
import os

HOST = '0.0.0.0'
PORT = 8000

clients = {}
clients_lock = threading.Lock()

def broadcast(message, sender=None):
    with clients_lock:
        for client_id, conn in clients.items():
            if client_id != sender:
                try:
                    conn.send(message.encode('utf-8'))
                except:
                    pass

def handle_client(conn, addr):
    client_id = f"{addr[0]}:{addr[1]}"
    username = None
    
    with clients_lock:
        clients[client_id] = conn
    
    print(f"[{client_id}] Подключился")
    
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            
            try:
                msg = json.loads(data.decode('utf-8'))
                
                if msg.get('type') == 'login':
                    username = msg.get('username', 'Anonymous')
                    broadcast(json.dumps({
                        'type': 'system',
                        'message': f'{username} присоединился к чату'
                    }), sender=client_id)
                    
                elif msg.get('type') == 'message' and username:
                    broadcast_msg = json.dumps({
                        'type': 'message',
                        'username': username,
                        'message': msg.get('message', ''),
                        'timestamp': msg.get('timestamp', '')
                    })
                    broadcast(broadcast_msg)
                    
            except json.JSONDecodeError:
                pass
                
    except Exception as e:
        print(f"[{client_id}] Ошибка: {e}")
    finally:
        with clients_lock:
            if client_id in clients:
                del clients[client_id]
        
        if username:
            broadcast(json.dumps({
                'type': 'system',
                'message': f'{username} покинул чат'
            }))
        
        conn.close()
        print(f"[{client_id}] Отключился")

def main():
    print(f"Запуск сервера на {HOST}:{PORT}")
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(10)
    
    print(f"Сервер запущен! Откройте http://localhost:{PORT} в браузере")
    print(f"Для остановки нажмите Ctrl+C")
    
    try:
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\nСервер остановлен")
    finally:
        server.close()

if __name__ == '__main__':
    main()
