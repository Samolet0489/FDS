# HPC MPI Fraud Prediction Service

A high-performance, parallelized fraud detection microservice designed to scale across multiple processors. This service uses mpi4py and a pre-trained machine learning model to perform batch predictions on transaction data pulled from a queue, then returns results to another queue.

---

## Repository Structure


```
├── mpi_prediction_service
│   ├── Dockerfile
│   ├── README.md
│   ├── fraud_rf_model.pkl
│   ├── mpi_service.py
│   └── requirements.txt
```


### File Descriptions

   - **mpi_service.py**: Core Python script implementing the fraud detection microservice using MPI. Rank 0 pulls transactions from a queue, scatters them to worker ranks, gathers predictions, and pushes results to the output queue.
   - **fraud_rf_model.pkl**: Pre-trained Random Forest model used for fraud classification. Loaded once at startup and used across all ranks.
   - **requirements.txt**: Python dependencies for the service.
   - **Dockerfile**: Builds the container environment for the service.

---

## Prerequisites

- Python 3.10+
- mpi4py and OpenMPI
- Docker and Docker Compose

---

## Configuration

The service relies on the following environment variables:

```yaml
MQ_URL=http://message_queue_service:7500
AUTH_SERVICE_URL=http://auth_service:5001
MQ_USER=<username>
MQ_PASSWORD=<password>
TRANSACTION_QUEUE=transactions
RESULTS_QUEUE=results
MODEL_PATH=fraud_rf_model.pkl
```

## Dependencies are listed in `requirements.txt`:

```
mpi4py==3.1.4
scikit-learn==1.6.1
requests
pyyaml
joblib>=1.3
```

## How it works

**Model Loading**: Loads a scikit-learn model at startup.

**Batch Processing**:
- Rank 0 pulls up to P transactions from a queue.
- Tasks are distributed to all available MPI worker ranks (including itself).

**Prediction**:
- Each rank predicts fraud using the ML model.
- Results include transaction ID, timestamp, fraud flag, and confidence score.

**Result Handling**:
- Rank 0 gathers all predictions.
- Successfully predicted results are pushed to a results queue.

**Repeat**: The system loops indefinitely, handling new batches as they arrive.

---

## Build & Run

### With Docker

1. **Build the image**

   ```bash
   docker-compose build 
   ```

2. **Run the container**

   ```bash
   docker-compose up -d
   ```

## Persistence & Testing

* This service integrates with the previously implemented queue service, which handles persistent message queues.
* On startup, the service connects to the transaction queue to pull messages.
* Results are written back to a separate results queue.

### Quick Test

1. **Create both transactions and results queue** (admin token required):

   ```bash
   POST http://localhost:7500/queues/transactions \
     -H "Authorization: <ADMIN_TOKEN>"
   ```

   ```bash
   POST http://localhost:7500/queues/results \
     -H "Authorization: <ADMIN_TOKEN>"
   ```
2. **Push a message**:
   - an existing transaction with a valid ID is needed
   ```bash
   POST http://localhost:7500/queues/transactions/push \
     -H "Authorization: <ADMIN_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
         "transaction_id": 3
         }'
   ```

3. **Pull the message** (Valid token required):

   ```bash
    POST http://localhost:7500/queues/results/pull \
    -H "Authorization: <ADMIN_TOKEN>"
   ```

---

## Authentication & Roles

All endpoints require a valid token in the `Authorization` header.

* **Administrators**: create/delete queues, push, pull
* **Agents**: list queues, push, pull

---

## Logging

Each rank logs its own activity with detailed timestamped output, including:

* Rank ID
* Queue pull events
* Predictions and confidence
* Errors with transaction ID

---


## Authors

 **Alexander Savov and Balazs Madarasi**  
 IMC Krems – SS 2025

---