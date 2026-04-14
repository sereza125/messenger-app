import subprocess
import time
import os

# Start ngrok tunnel
print("Starting ngrok tunnel...")
ngrok_path = os.path.join(os.path.dirname(__file__), "ngrok.exe")

# Try to start ngrok
process = subprocess.Popen(
    [ngrok_path, "http", "8010"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

print("Ngrok started! Waiting for tunnel URL...")
print("Note: If this is first run, you'll need to sign up at https://ngrok.com")
print("and run: ngrok authtoken YOUR_TOKEN")
print("\nTunnel should be available shortly at ngrok.io")

# Keep the script running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping tunnel...")
    process.terminate()
