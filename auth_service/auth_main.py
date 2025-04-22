# auth_main.py
import base64, os
from flask import Flask, request, jsonify
from functools import wraps

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
    """
    Generates a random base64-encoded token, stores it in TOKENS,
    and returns the token string.
    """

    random_bytes = os.urandom(12)
    token_str = base64.b64encode(random_bytes).decode('utf-8')
    TOKENS[token_str] = {"username": username, "role": role}
    return token_str


def verify_token_internal(token: str):
    """
    Internal function to look up the token in TOKENS.
    Returns (True, role) if valid, otherwise (False, None).
    """
    if token in TOKENS:
        role = TOKENS[token]["role"]
        return (True, role)
    return (False, None)

def admin_only(f):
    """
    Decorator that ensures the caller has a valid token with role=administrator.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get("Authorization", "")
        valid, role = verify_token_internal(token)
        if not valid or role != "administrator":
            return jsonify({"error": "Forbidden - Admin only."}), 403
        return f(*args, **kwargs)
    return wrapper


@app.before_request
def log_request_info():
    """
    Logs inbound request information: source IP, method/path, headers, and body.
    """
    app.logger.info("------ REQUEST START ------")
    app.logger.info(f"Source: {request.remote_addr}")
    app.logger.info(f"method/Patch: {request.method} {request.path}")
    app.logger.info(f"Headers: {dict(request.headers)}")
    try:
        # attempt to log JSON body if present
        if request.is_json:
            app.logger.info(f"Body: {request.get_json()}")
        else:
            app.logger.info(f"Body: [Not JSON or empty]")
    except Exception as e:
        app.logger.warning(f"Could not read request body: {e}")
        
@app.after_request
def log_response_info(response):
    """
    Logs response status code and headers.
    """
    app.logger.info(f"Status: {response.status_code}")
    app.logger.info(f"Response Headers: {dict(response.headers)}")
    app.logger.info("------ REQUEST END ------\n")
    return response



################# DOCUMENT THIS BETTER!!!!! #######################

# Auth Endpoints
@app.route('/auth/login', methods=['POST'])
def login():
    """
    Expects JSON: {"username": "...", "password": "..."}
    Returns: {"token": "...", "role": "..."}
    - If valid credentials, issues a new token and stores it in TOKENS.
    - If invalid, returns 401 with {"error": "Invalid credentials"}.
    """
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    # Basic validation
    if not username or not password:
        return jsonify({"error": "Invalid input"}), 400

    if len(data) != 2:
        return jsonify({"error": "Invalid input"}), 400

    # check credentials
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
    data = request.json or {}
    token_str = data.get("token", "")

    valid, role = verify_token_internal(token_str)
    if valid:
        app.logger.info(f"VERIFY: token={token_str} is valid, role={role}") # comment me
        return jsonify({"valid": True, "role": role}), 200
    else:
        app.logger.info(f"VERIFY: token={token_str} is NOT valid.")
        return jsonify({"valid": False}), 401

    
@app.route('/auth/create_user', methods=['POST'])
@admin_only
def create_user():
    '''
    Creates a new user in the in-memory USER_DATA store.
    Expects JSON: { "username": "...", "password": "...", "role": "..." }
    Only allowed if the caller is an administrator.
    '''
    data = request.json or {}
    new_username = data.get("username")
    new_password = data.get("password")
    new_role = data.get("role")

    # basic validation
    if not new_username or not new_password or not new_role:
        return jsonify({"error": "Missing username, password, or role"}), 400

    # Check if user already exists
    if new_username in USER_DATA:
        return jsonify({"error": "User already exists"}), 400
    
    # Add the new user in memory
    USER_DATA[new_username] = {
        "password": new_password,
        "role": new_role
    }

    app.logger.info(f"Admin created user: {new_username} with role = {new_role}")
    return jsonify({"message": f"User '{new_username}' created successfully."}), 201


@app.route('/auth/delete_user/<username>', methods=['DELETE'])
@admin_only
def delete_user(username):
    """
    Deletes a user from the in-memory USER_DATA store.
    Only allowed if the caller is an administrator.
    """
    if username not in USER_DATA:
        return jsonify({"error": f"User '{username}' does not exist"}), 404

    # remove from the user store
    del USER_DATA[username]

    app.logger.info(f"Admin deleted user: {username}")
    return jsonify({"message": f" User '{username}' deleted successfully."}), 200
    

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)
