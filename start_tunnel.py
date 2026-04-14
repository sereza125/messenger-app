#!/usr/bin/env python3
import subprocess
import time
import sys
import os

def main():
    # Start server in background
    print("Starting server...")
    server = subprocess.Popen(
        [sys.executable, "telegram_server.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    time.sleep(2)
    
    # Check if ngrok exists
    ngrok_path = os.path.join(os.path.dirname(__file__), "ngrok.exe")
    if not os.path.exists(ngrok_path):
        print("ngrok.exe not found, downloading...")
        subprocess.run([
            "curl", "-L", "-o", "ngrok.zip",
            "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-windows-amd64.zip"
        ], check=True)
        subprocess.run(["tar", "-xf", "ngrok.zip"], check=True)
    
    # Start ngrok
    print("Starting ngrok tunnel...")
    ngrok = subprocess.Popen(
        [ngrok_path, "http", "8011", "--log=stdout"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Read and display ngrok URL
    print("\n" + "="*50)
    print("Waiting for tunnel URL...")
    print("="*50 + "\n")
    
    try:
        for line in ngrok.stdout:
            print(line, end='')
            if "url=" in line.lower() or "forwarding" in line.lower():
                print(f"\n\n🔗 TUNNEL ACTIVE: Check output above for URL")
    except KeyboardInterrupt:
        print("\n\nStopping...")
        ngrok.terminate()
        server.terminate()

if __name__ == "__main__":
    main()
