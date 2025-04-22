# transaction_main.py

import os
import time
import psycopg2
import requests
from flask import Flask, request, jsonify
from functools import wraps
app = Flask(__name__)


# tid = transaction_id
# ts = timestamp
# amt = amount




# -------------------------------------------------------------------------------------
#  READ ENVIRONMENT VARIABLES (useful for Docker Compose)
# -------------------------------------------------------------------------------------
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_USER = os.environ.get('DB_USER', 'myuser')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'mypassword')
DB_NAME = os.environ.get('DB_NAME', 'transactions_db')

# URL of your Authentication service
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://localhost:5001')

# -------------------------------------------------------------------------------------
#  DATABASE CONNECTION & INITIALIZATION
# -------------------------------------------------------------------------------------
def get_db_connection():
    """Establish a new connection to the PostgreSQL database."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )

def wait_for_db(timeout=30):
    """Wait for the database to be ready, retrying until a connection is successful or timeout is reached."""
    start_time = time.time()
    while True:
        try:
            conn = get_db_connection()
            conn.close()
            app.logger.info("Database is ready!")
            break
        except psycopg2.OperationalError:
            if time.time() - start_time > timeout:
                app.logger.error("Timed out waiting for the database.")
                raise
            app.logger.info("Waiting for database to be ready...")
            time.sleep(1)

def init_db():
    """Create the needed tables if they don't exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # transactions table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            customer VARCHAR(255) NOT NULL,
            timestamp VARCHAR(255) NOT NULL,
            status VARCHAR(10) NOT NULL,
            vendor_id VARCHAR(255) NOT NULL,
            amount DOUBLE PRECISION
        );
    ''')
    
    # results table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            transaction_id INTEGER NOT NULL,
            timestamp VARCHAR(255) NOT NULL,
            is_fraudulent BOOLEAN,
            confidence DOUBLE PRECISION,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id)
        );
    ''')
    
    conn.commit()
    cur.close()
    conn.close()

# Wait for the DB to be ready before initializing it
wait_for_db()
init_db()

# -------------------------------------------------------------------------------------
#  AUTH TOKEN VERIFICATION
# -------------------------------------------------------------------------------------

# #test code:
# def verify_token(token):
#     # Temporary bypass for testing:
#     return True, "administrator"



@app.before_request
def log_request_info():
    """
    Logs inbound request information: source IP, method/path, headers, and body.
    """
    app.logger.info("------ REQUEST START ------")
    app.logger.info(f"Source: {request.remote_addr}")
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
    """
    Logs outbound response status and headers.
    """
    app.logger.info(f"Status: {response.status_code}")
    app.logger.info(f"Response Headers: {dict(response.headers)}")
    app.logger.info("------ REQUEST END ------\n")
    return response


def verify_token(token):
    """
    Call the Auth service to verify the token and get the role.
    Return (True, role) if valid, else (False, None).
    """
    if not token:
        return False, None
    
    try:
        resp = requests.post(f"{AUTH_SERVICE_URL}/auth/verify", json={"token": token})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("valid", False):
                return True, data.get("role")
    except Exception as e:
        app.logger.error(f"Error verifying token: {e}")
    
    return False, None




def role_check(allowed_roles):
    """
    Decorator that ensures the user has one of the allowed roles.
    Verifies the token by calling the Auth service and checks role membership.
    Returns 403 if unauthorized.
    """
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


# -------------------------------------------------------------------------------------
#  ENDPOINTS
# -------------------------------------------------------------------------------------

@app.route("/transactions", methods=["POST"])
@role_check(["administrator", "agent"])
def create_transaction():
    """
    Create a new transaction.
    Requires JSON with: customer, timestamp, vendor_id, amount.
    Defaults status to 'submitted'.
    """
    data = request.json or {}
    customer = data.get("customer")
    timestamp = data.get("timestamp")
    vendor_id = data.get("vendor_id")
    amount = data.get("amount")
    
    # Basic validation
    if not all([customer, timestamp, vendor_id, amount is not None]):
        return jsonify({"error": "Missing required fields"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO transactions (customer, timestamp, status, vendor_id, amount)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', (customer, timestamp, "submitted", vendor_id, amount))
    
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    app.logger.info(f"Created transaction with ID={new_id}")
    return jsonify({"message": "Transaction created", "transaction_id": new_id}), 201

@app.route("/transactions/<int:tid>", methods=["PUT"])
@role_check(["administrator", "agent"])
def update_transaction(tid):
    """
    Update an existing transaction's status.
    Expects JSON: { "status": "submitted/accepted/rejected" }
    """
    data = request.json or {}
    status = data.get("status")
    
    if status not in ["submitted", "accepted", "rejected"]:
        return jsonify({"error": "Invalid or missing status"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE transactions SET status=%s WHERE id=%s', (status, tid))
    
    if cur.rowcount == 0:
        # No rows updated => transaction not found
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": "Transaction not found"}), 404
    
    conn.commit()
    cur.close()
    conn.close()

    app.logger.info(f"Updated transaction ID={tid} to status={status}")
    return jsonify({"message": "Transaction updated"}), 200

@app.route("/transactions/<int:tid>/results", methods=["GET"])
@role_check(["administrator", "agent"])
def get_results(tid):
    """
    Fetch the prediction results for a transaction.
    Only accessible to administrator/agent roles.
    """

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'SELECT id, transaction_id, timestamp, is_fraudulent, confidence '
        'FROM results WHERE transaction_id=%s',
        (tid,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    results_data = []
    for row in rows:
        rid, transaction_id, ts, is_fraud, conf = row
        results_data.append({
            "result_id": rid,
            "transaction_id": transaction_id,
            "timestamp": ts,
            "is_fraudulent": is_fraud,
            "confidence": conf
        })
    
    app.logger.info(f"Fetched {len(results_data)} results for transaction ID={tid}")
    return jsonify({"results": results_data}), 200


@app.route("/transactions", methods=["GET"])
@role_check(["administrator", "agent", "secretary"])
def list_transactions():
    """
    Return all transactions (basic data).
    Secretary (read-only), Agent, and Admin can call this.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, customer, timestamp, status, vendor_id, amount FROM transactions")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # format rows
    results = []
    for row in rows:
        tid, customer, ts, status, vend, amt = row
        results.append({
            "id": tid,
            "customer": customer,
            "timestamp": ts,
            "status": status,
            "vendor_id": vend,
            "amount": amt
        })
    app.logger.info(f"Fetched{len(results)} transactions (read-only)")
    return jsonify({"transactions": results}), 200


@app.route("/transactions/<int:tid>", methods=["GET"])
@role_check(["administrator", "agent", "secretary"])
def get_transaction(tid):
    """
    Return one transaction's details by ID.
    Secretary, Agent, or Admin can call this (read-only).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, customer, timestamp, status, vendor_id, amount
        FROM transactions
        WHERE id = %s
    """, (tid,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "Transaction not found"}), 404
    
    tid, customer, ts, status, vend, amt = row
    transaction_data = {
        "id": tid,
        "customer": customer,
        "timestamp": ts,
        "status": status,
        "vendor_id": vend,
        "amount": amt
    }
    app.logger.info(f"Fetched transactions (read-only) ID={tid}")
    return jsonify({"transaction": transaction_data}), 200




# -------------------------------------------------------------------------------------
#  RUN THE SERVICE
# -------------------------------------------------------------------------------------

if __name__ == "__main__":
    # For Docker, listen on all interfaces (0.0.0.0).
    app.run(host="0.0.0.0", port=5002, debug=True)
