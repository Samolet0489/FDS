# HPC Queue Service

A lightweight message-queue microservice (Flask + Python 3.10) for front-ending compute workers on port **7500**. It supports:

- Dynamic creation & deletion of named queues (administrators only)
- Push & pull of JSON messages (administrators & agents)
- Configurable maximum messages per queue
- Periodic persistence to disk and state restoration on restart
- Full request/response logging

---

## Repository Structure


```
├── Dockerfile
├── README.md
├── config.yaml
├── requirements.txt
├── queue_main.py
├── queue_manager.py
├── persistence.py
└── queues.json             ← created at runtime by persistence.py (located in the docker)
```


### File Descriptions

   - **config.yaml**: Holds runtime configuration parameters that the application reads at startup
   - **queue_main.py**: Implements the Flask-based HTTP API: routes for listing, creating, deleting queues, plus push and pull operations; enforces role-based access via token verification; and starts a background thread for periodic persistence while handling logging.
   - **queue_manager.py**: Contains the QueueManager class that holds the in-memory queue dictionary, enforces thread-safe create/delete/push/pull operations, and delegates to persistence.py for saving and loading state.
   - **persistence.py**: Provides load_state() and save_state() functions that read from and write to queues.json on disk. Ensures the service can recover its queues after a restart by periodically persisting the in-memory state.
  


---

## Prerequisites

- Docker and Docker Compose
- Python 3.10 

---

## Configuration

Edit `config.yaml` to set service parameters:

```yaml
max_queue_size:           100           # Max messages per queue
persist_interval_seconds: 60            # Persistence interval in seconds
auth_service_url:         "http://auth_service:5001"  # Auth service URL
transaction_service_url:  "http://transaction_service:5002"  # Transaction service URL
````

Dependencies are listed in `requirements.txt`:

```
flask
pyyaml
requests
```

---

## Build & Run

### With Docker

1. **Build the image**

   ```bash
   docker-compose build 
   ```

2. **Run the container (with host persistence)**

   ```bash
   docker-compose up -d
   ```

## Persistence & Testing

* On startup, if `queues.json` exists in the working directory, its queues load into memory.
* Every `persist_interval_seconds` (default 60s), all queues are saved back to `queues.json`.
* On restart, the service restores its state from the file.

### Quick Test

1. **Create a queue** (admin token required):

   ```bash
   POST http://localhost:7500/queues/test \
     -H "Authorization: <ADMIN_TOKEN>"
   ```
2. **Push a message**:
   - an existing transaction with a valid ID is needed
   ```bash
   POST http://localhost:7500/queues/test/push \
     -H "Authorization: <ADMIN_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
         "transaction_id": 3,
         "customer": "Alice",
         "timestamp": "2025-05-11T12:00:00Z",
         "amount": 123.45
         }'
   ```
3. **Check persistence**:

   After runing the container for at least 60 seconds it will create a json file containing the queues.

   ```
   In the ds-queue-service container -> Files -> app/data/queues.json
   ```
4. **Restart service**:

   After the creation of the queues.json file, the service can be restarted to check that the queues are actually saved and can be restored


5. **Pull the message** (Valid token required):

   ```bash
   POST http://localhost:7500/queues/test/pull \
     -H "Authorization: <ADMIN_TOKEN>"
   ```

---

## Authentication & Roles

All endpoints require a valid token in the `Authorization` header.

* **Administrators**: create/delete queues, push, pull
* **Agents**: list queues, push, pull
* **Secretaries**: list queues only

---

## Logging

Requests and responses are logged (Flask’s default logger) with:

* Source IP, destination host
* HTTP method, path
* Headers and JSON body (if present)
* Response status and headers

---


## Authors

 **Alexander Savov and Balazs Madarasi**  
 IMC Krems – SS 2025

---