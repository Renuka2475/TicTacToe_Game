import requests
import base64
import json

# Nakama server details
NAKAMA_HOST = "127.0.0.1"
NAKAMA_PORT = 7350
SERVER_KEY = "defaultkey"

# Encode server key in Base64 (for authentication)
basic_auth = base64.b64encode(f"{SERVER_KEY}:".encode()).decode()

# Create a user or login (email + password)
url = f"http://{NAKAMA_HOST}:{NAKAMA_PORT}/v2/account/authenticate/email?create=true"

payload = {
    "email": "player1@example.com",
    "password": "password123"
}

headers = {
    "Authorization": f"Basic {basic_auth}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

response = requests.post(url, headers=headers, data=json.dumps(payload))

if response.status_code == 200:
    print("✅ Connected successfully!")
    print("Session token:", response.json()["token"])
else:
    print("❌ Failed to connect")
    print(response.text)
