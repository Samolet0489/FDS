# auth_main.py
import base64, os
from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory user store: {username: {"password": ..., "role": ...}}
USER_DATA = {
    "admin": {"password": "adminpass", "role": "administrator"},
    "sec": {"password": "secpass", "role": "secretary"},
    "agent": {"password": "agentpass", "role": "agent"}
}

# In-memory token store: {token_string: {"username": ..., "role": ...}}
TOKENS = {}

def generate_token(username, role):
    random_bytes = os.urandom(12)
    token_str = base64.b64encode(random_bytes).decode('utf-8')
    TOKENS[token_str] = {"username": username, "role": role}
    return token_str

@app.route('/auth/login', methods=['POST'])
def login():
    """
    Expects JSON: {"username": "...", "password": "..."}
    Returns: {"token": "...", "role": "..."}
    """
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    if username in USER_DATA and USER_DATA[username]["password"] == password:
        role = USER_DATA[username]["role"]
        token_str = generate_token(username, role)
        # Log the login
        app.logger.info(f"LOGIN: user={username}, role={role}, token={token_str}")
        return jsonify({"token": token_str, "role": role}), 200
    else:
        # Log the failed login
        app.logger.warning("Failed login attempt.")
        return jsonify({"error": "Invalid credentials"}), 401

@app.route('/auth/verify', methods=['POST'])
def verify():
    """
    Expects JSON: {"token": "..."}
    Returns: {"valid": True/False, "role": "..."} if valid
    """
    data = request.json
    token_str = data.get("token")

    if token_str in TOKENS:
        info = TOKENS[token_str]
        app.logger.info(f"VERIFY: token={token_str} is valid.")
        return jsonify({"valid": True, "role": info["role"]}), 200
    else:
        app.logger.info(f"VERIFY: token={token_str} is NOT valid.")
        return jsonify({"valid": False}), 401

if __name__ == '__main__':
    app.run(port=5001, debug=True)
