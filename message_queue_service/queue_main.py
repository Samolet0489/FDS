import threading
import time
import yaml
import requests
import os
from flask import Flask, request, jsonify
from functools import wraps
from queue_manager import QueueManager

app = Flask(__name__)

# -----------------------------------------------------------------------------
#  LOAD CONFIGURATION
# -----------------------------------------------------------------------------
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

MAX_QUEUE_SIZE = config.get("max_queue_size", 100)
PERSIST_INTERVAL = config.get("persist_interval_seconds", 60)
AUTH_SERVICE_URL = config.get("auth_service_url", "http://auth_service:5001")

# -----------------------------------------------------------------------------
#  QUEUE MANAGER INSTANCE
# -----------------------------------------------------------------------------
qm = QueueManager(max_size=MAX_QUEUE_SIZE)

# -----------------------------------------------------------------------------
#  PERSISTENCE BACKGROUND THREAD
# -----------------------------------------------------------------------------
def _persistence_loop():
    while True:
        time.sleep(PERSIST_INTERVAL)
        try:
            qm.persist()
            app.logger.info("Persisted queue state to disk.")
        except Exception as e:
            app.logger.warning(f"Failed to persist queue state: {e}")

if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    threading.Thread(target=_persistence_loop, daemon=True).start()

# -----------------------------------------------------------------------------
#  REQUEST/RESPONSE LOGGING (same style as other services)
# -----------------------------------------------------------------------------
@app.before_request
def log_request_info():
    app.logger.info("------ REQUEST START ------")
    app.logger.info(f"Source: {request.remote_addr}")
    app.logger.info(f"Destination: {request.host}")
    app.logger.info(f"Method/Path: {request.method} {request.path}")
    app.logger.info(f"Headers: {dict(request.headers)}")
    try:
        if request.is_json:
            app.logger.info(f"Body: {request.get_json()}")
        else:
            app.logger.info("Body: [Not JSON or empty]")
    except Exception as e:
        app.logger.warning(f"Could not read request body: {e}")

@app.after_request
def log_response_info(response):
    app.logger.info(f"Status: {response.status_code}")
    app.logger.info(f"Response Headers: {dict(response.headers)}")
    app.logger.info("------ REQUEST END ------\n")
    return response

# -----------------------------------------------------------------------------
#  AUTH TOKEN VERIFICATION
# -----------------------------------------------------------------------------
def verify_token(token: str):
    if not token:
        return False, None
    try:
        resp = requests.post(f"{AUTH_SERVICE_URL}/auth/verify", json={"token": token})
        if resp.status_code == 200:
            data = resp.json()
            return data.get("valid", False), data.get("role")
    except Exception as e:
        app.logger.error(f"Error verifying token with Auth service: {e}")
    return False, None


def role_check(allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = request.headers.get("Authorization", "")
            valid, role = verify_token(token)
            if not valid or role not in allowed_roles:
                return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# -----------------------------------------------------------------------------
#  QUEUE ENDPOINTS
# -----------------------------------------------------------------------------
@app.route("/queues", methods=["GET"])
@role_check(["administrator", "agent", "secretary"])
def list_queues():
    try:
        names = qm.list_queues()
        return jsonify({"queues": names}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/queues/<queue_name>", methods=["POST"])
@role_check(["administrator"])
def create_queue(queue_name):
    try:
        qm.create_queue(queue_name)
        return jsonify({"message": f"Queue '{queue_name}' created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/queues/<queue_name>", methods=["DELETE"])
@role_check(["administrator"])
def delete_queue(queue_name):
    try:
        qm.delete_queue(queue_name)
        return jsonify({"message": f"Queue '{queue_name}' deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/queues/<queue_name>/push", methods=["POST"])
@role_check(["administrator", "agent"])
def push_message(queue_name):
    try:
        message = request.json or {}
        tid = message.get("transaction_id")
        if not tid:
            return jsonify({"error": "Missing transaction_id in message"}), 400
        
        headers = {"Authorization": request.headers.get("Authorization", "")}
        ts_url = config["transaction_service_url"]
        resp  =requests.get(f"{ts_url}/transactions/{tid}", headers=headers)
        if resp.status_code != 200:
            return jsonify({"error": "Transaction not found"}), 404
        
        existing = qm.queues.get(queue_name, [])
        if any(msg.get("transaction_id") == tid for msg in existing):
            return jsonify({"error" : f"Transaction {tid} already in queue"}), 400

        qm.push(queue_name, message)
        return jsonify({"message": "Message pushed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/queues/<queue_name>/pull", methods=["POST"])
@role_check(["administrator", "agent"])
def pull_message(queue_name):
    try:
        msg = qm.pull(queue_name)
        return jsonify({"message": msg}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# -----------------------------------------------------------------------------
#  START THE SERVICE
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Use debug=True for development; remove in production
    app.run(host="0.0.0.0", port=7500, debug=True, use_reloader=False)
