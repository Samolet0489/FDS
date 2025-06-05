#!/usr/bin/env python
"""
Parallel fraud-prediction service (MPI + message-queue) with detailed logging.
"""
import os
import time
import json
import logging
import requests
from joblib import load as jl  
from mpi4py import MPI


print("CAR")

# ─── Logging config ───────────────────────────────────────────────────────────
def configure_logger(rank: int) -> logging.Logger:
    fmt = f"%(asctime)s [rank {rank}] %(levelname)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt="%H:%M:%S")
    return logging.getLogger(f"rank{rank}")

# ─── Configuration ────────────────────────────────────────────────────────────
MQ_URL     = os.getenv("MQ_URL", "http://message_queue_service:7500")
AUTH_URL   = os.getenv("AUTH_SERVICE_URL", "http://auth_service:5001")
MQ_USER    = os.getenv("MQ_USER")
MQ_PASSWORD= os.getenv("MQ_PASSWORD")
TX_QUEUE   = os.getenv("TRANSACTION_QUEUE", "transactions")
RES_QUEUE  = os.getenv("RESULTS_QUEUE", "results")
MODEL_PATH = os.getenv("MODEL_PATH", "fraud_rf_model.pkl")

# ─── Authentication helper ────────────────────────────────────────────────────
def fetch_token() -> str:
    token = os.getenv("MQ_TOKEN")
    if token:
        return token
    if not (MQ_USER and MQ_PASSWORD):
        raise RuntimeError("Need MQ_TOKEN or MQ_USER/MQ_PASSWORD env vars")
    r = requests.post(
        f"{AUTH_URL}/auth/login",
        json={"username": MQ_USER, "password": MQ_PASSWORD},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()["token"]

TOKEN   = fetch_token()
HEADERS = {"Authorization": TOKEN}

# ─── Load model ───────────────────────────────────────────────────────────────
def load_model(path: str):
    return jl(path)   


model = load_model(MODEL_PATH)
N_FEATURES = getattr(model, "n_features_in_", 2)

# ─── MPI setup ────────────────────────────────────────────────────────────────
COMM = MPI.COMM_WORLD
RANK = COMM.Get_rank()
SIZE = COMM.Get_size()
LOG  = configure_logger(RANK)

# ─── Queue helpers ────────────────────────────────────────────────────────────
#REMOVE IF THE new one WORKS
def pull_one(blocking: bool = True):
    """Pop a single transaction or return None."""
    url = f"{MQ_URL}/queues/{TX_QUEUE}/pull"
    payload = {"max_messages": 1}
    while True:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            return resp.json()["message"]
        if not blocking:
            return None
        time.sleep(2)

# ─── Queue helpers ────────────────────────────────────────────────────────────
# ─── Queue helpers ────────────────────────────────────────────────────────────
def pull_batch(n: int, *, blocking: bool = True) -> list[dict]:
    """
    Pull up to *n* transaction messages in one HTTP call.

    Works with queue APIs that return either {"messages":[…]} or {"message":{…}}.
    """
    url     = f"{MQ_URL}/queues/{TX_QUEUE}/pull"
    payload = {"max_messages": n}

    while True:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # normalise to a list
            if "messages" in data:              # batch API
                msgs = data["messages"]
            elif "message" in data and data["message"]:
                msgs = [data["message"]]        # single object
            else:
                msgs = []

            if msgs or not blocking:
                return msgs
        if not blocking:
            return []
        time.sleep(2)           # queue empty → wait and retry



def push_result(msg: dict):
    url = f"{MQ_URL}/queues/{RES_QUEUE}/push"
    r = requests.post(url, json=msg, headers=HEADERS, timeout=5)
    r.raise_for_status()

# ─── Master rank ──────────────────────────────────────────────────────────────
if RANK == 0:
    LOG.info("MPI service up with %d ranks", SIZE)

    while True:
        # 1. Pull at most SIZE messages
        # batch = []
        # for i in range(SIZE):
        #     tx = pull_one(blocking=(i == 0))
        #     if tx is None:
        #         break
        #     batch.append(tx)
        
        # instead of the above we do this so that we can do a BATcH
        batch = pull_batch(SIZE, blocking=True)

        if not batch:
            continue

        LOG.info("pulled %d tx: %s",
                 len(batch),
                 ", ".join(str(t['transaction_id']) for t in batch))

        # 2. Scatter to workers
        batch.extend([None] * (SIZE - len(batch)))
        my_task = COMM.scatter(batch, root=0)
        print("YELLOW")

        # run infrance locally if we got a task
        def infer(tx):
            amount = float(tx.get("amount", 0.0))
            X = [[amount] + [0.0] * (N_FEATURES - 1)]
            return {
                "transaction_id": tx["transaction_id"],
                "timestamp":      tx.get("timestamp"),
                "is_fraudulent":  bool(model.predict(X)[0]),
                "confidence":     float(max(model.predict_proba(X)[0])),
            }
        
        my_result = infer(my_task) if my_task else None

        # 3. Gather results
        results = COMM.gather(my_result, root=0)
        LOG.debug("gather returned: %s", results)

        # 4. Push valid results
        pushed = 0
        for res in results:
            if res:
                try:
                    push_result(res)
                    pushed += 1
                except Exception as ex:
                    LOG.error("push_result failed for tx %s: %s",
                              res.get("transaction_id"), ex)
        LOG.info("pushed %d result(s) to '%s'", pushed, RES_QUEUE)

# ─── Worker ranks ─────────────────────────────────────────────────────────────
else:
    while True:
        task = COMM.scatter(None, root=0)
        if task is None:
            COMM.gather(None, root=0)
            continue

        tid = task.get("transaction_id")
        LOG.info("received tx %s", tid)

        try:
            amount = float(task.get("amount", 0.0))
            X = [amount] + [0.0] * (N_FEATURES - 1)
            X = [X]

            fraud      = bool(model.predict(X)[0])
            confidence = float(max(model.predict_proba(X)[0]))

            result = {
                "transaction_id": tid,
                "timestamp":      task.get("timestamp"),
                "is_fraudulent":  fraud,
                "confidence":     confidence,
            }
            COMM.gather(result, root=0)
            LOG.info("predicted tx %s → fraud=%s conf=%.3f",
                     tid, fraud, confidence)
        except Exception as exc:
            LOG.error("ERROR on tx %s: %s", tid, exc)
            COMM.gather(None, root=0)
