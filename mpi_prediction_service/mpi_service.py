#!/usr/bin/env python
import os
import time
import pickle
import requests
from mpi4py import MPI

# ─── Configuration ─────────────────────────────────────────────────────────────
MQ_URL           = os.environ.get("MQ_URL", "http://message_queue_service:7500")
AUTH_URL         = os.environ.get("AUTH_SERVICE_URL", "http://auth_service:5001")
MQ_USER          = os.environ.get("MQ_USER")
MQ_PASSWORD      = os.environ.get("MQ_PASSWORD")
TRANSACTION_Q    = os.environ.get("TRANSACTION_QUEUE", "transactions")
RESULTS_Q        = os.environ.get("RESULTS_QUEUE", "results")
MODEL_PATH       = os.environ.get("MODEL_PATH", "fraud_rf_model.pkl")

# ─── Authentication helper (use our existing auth service) ─────────────────────
def get_token():
    """Get MQ token: prefer existing env, otherwise login via auth service"""
    token = os.environ.get("MQ_TOKEN")
    if token:
        return token
    if not (MQ_USER and MQ_PASSWORD):
        raise RuntimeError("MQ_TOKEN or MQ_USER and MQ_PASSWORD must be set")

    # Login to auth service
    resp = requests.post(
        f"{AUTH_URL}/auth/login",
        json={"username": MQ_USER, "password": MQ_PASSWORD}
    )
    resp.raise_for_status()
    return resp.json().get("token")

# Fetch token and prepare headers
MQ_TOKEN = get_token()
headers = {"Authorization": MQ_TOKEN}

# ─── Load the pre-trained RF model ─────────────────────────────────────────────
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

# ─── MPI setup ───────────────────────────────────────────────────────────────────
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# ─── Message queue helpers ──────────────────────────────────────────────────────

def pull_transaction(blocking=True):
    url = f"{MQ_URL}/queues/{TRANSACTION_Q}/pull"
    while True:
        resp = requests.post(url, headers=headers)
        if resp.status_code == 200:
            return resp.json().get("message")
        if not blocking:
            return None
        time.sleep(1)


def push_result(result_msg):
    url = f"{MQ_URL}/queues/{RESULTS_Q}/push"
    resp = requests.post(url, json=result_msg, headers=headers)
    resp.raise_for_status()

# ─── Master logic (rank 0) ───────────────────────────────────────────────────────
if rank == 0:
    print(f"[master] Starting MPI service with {size} ranks.")
    while True:
        # gather up to `size` transactions
        batch = []
        for i in range(size):
            tx = pull_transaction(blocking=(i == 0))
            if tx is None:
                break
            batch.append(tx)
        if not batch:
            time.sleep(2)
            continue

        # pad and scatter
        tasks = batch + [None] * (size - len(batch))
        comm.scatter(tasks, root=0)

        # collect predictions
        preds = comm.gather(None, root=0)
        for p in preds:
            if p:
                push_result(p)

# ─── Worker logic (ranks >0) ─────────────────────────────────────────────────────
else:
    while True:
        task = comm.scatter(None, root=0)
        if task is None:
            comm.gather(None, root=0)
            continue

        # perform prediction
        features = [[task.get("amount"), 0]]
        is_fraud = bool(model.predict(features)[0])
        confidence = float(max(model.predict_proba(features)[0]))

        result = {
            "transaction_id": task.get("transaction_id"),
            "timestamp": task.get("timestamp"),
            "is_fraudulent": is_fraud,
            "confidence": confidence
        }
        comm.gather(result, root=0)
