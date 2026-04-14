#!/usr/bin/env python3
import subprocess
import time
import sys
import os
import threading

def start_server():
    """Start the messenger server"""
    print("[+] Starting messenger server on port 8011...")
    return subprocess.Popen(
        [sys.executable, "telegram_server.py"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

def start_ngrok():
    """Start ngrok tunnel"""
    try:
        from pyngrok import ngrok
        print("[+] Starting ngrok tunnel...")
        # Start ngrok
        public_url = ngrok.connect(8011, "http")
        print(f"\n{'='*60}")
        print(f"🌐 PUBLIC URL: {public_url}")
        print(f"{'='*60}\n")
        print("Share this link with anyone!")
        return public_url
    except Exception as e:
        print(f"[!] Ngrok error: {e}")
        print("[!] Trying manual ngrok...")
        ngrok_path = os.path.join(os.path.dirname(__file__), "ngrok.exe")
        if os.path.exists(ngrok_path):
            subprocess.Popen([ngrok_path, "http", "8011"])
            print("[+] Ngrok started manually. Check http://localhost:4040 for URL")
        return None

def main():
    # Start server
    server = start_server()
    time.sleep(3)
    
    # Start tunnel
    try:
        url = start_ngrok()
    except:
        print("[!] Could not start tunnel. Server running locally on http://localhost:8011")
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[+] Stopping...")
        server.terminate()
        try:
            from pyngrok import ngrok
            ngrok.kill()
        except:
            pass

if __name__ == "__main__":
    main()
