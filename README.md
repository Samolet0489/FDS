# Distributed Systems Assignment 2 – Service-Oriented Architecture

## Overview

This project implements a simple service-oriented architecture for a fraud detection system. It consists of:

- **Authentication Service** (Flask)
- **Transaction Service** (Flask + PostgreSQL)
- **Role-Based Access Control**
- **Token-Based Authentication**
- **Dockerized Services using Docker Compose**

---

## Architecture

Each service runs in its own container and communicates via RESTful APIs.

- The **Authentication Service** handles login, token creation, and role validation.
- The **Transaction Service** manages customer transaction records and ML fraud prediction metadata.

> All access control is role-based and validated via tokens.

### File description of auth_main.py

This file implements the authentication service using Flask. It handles user login, token generation, role-based access control, and basic in-memory user and token management. It provides three main endpoints: /auth/login to authenticate users and issue tokens, /auth/verify to validate tokens and retrieve user roles, and /auth/create_user and /auth/delete_user for administrator-controlled user management. It also logs all request and response metadata, including source, destination, headers, and body content.

### File description of transaction_main.py

This file implements the transaction service using Flask and connects to a PostgreSQL database. It supports creating, updating, retrieving, and listing transactions, as well as viewing fraud detection results. The service uses role-based access by verifying tokens with the authentication service. It logs detailed information about each request and response, including source, destination, headers, and body. It initializes the database and creates required tables if they do not exist.

---

## Technologies

- Python 3.10
- Flask 
- PostgreSQL 15 
- Docker 


> We chose flask because we felt the most confident in using it as we have the most expirience working with that framework. It is also well-documnted and known, so when any issues accured we could find the solution online swiftly.
 

---

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### Launch the System

```bash
docker-compose up --build
```

This will:

- Start the PostgreSQL database
- Launch the `auth_service` on port **5001**
- Launch the `transaction_service` on port **5002**

---

## Authentication Service

**Base URL:** `http://localhost:5001`

| Method | Route                     | Description                |
|--------|---------------------------|----------------------------|
| POST   | `/auth/login`             | Login and get token        |
| POST   | `/auth/create_user`       | Create new user (admin)    |
| DELETE | `/auth/delete_user/<user>`| Delete user (admin)        |
| POST   | `/auth/verify`            | Verify token               |

---

## Transaction Service

**Base URL:** `http://localhost:5002`

| Method | Route                        | Access           | Description                        |
|--------|------------------------------|------------------|------------------------------------|
| POST   | `/transactions`              | Admin, Agent     | Create a transaction               |
| PUT    | `/transactions/<id>`         | Admin, Agent     | Update transaction status          |
| GET    | `/transactions`              | All roles        | List all transactions              |
| GET    | `/transactions/<id>`         | All roles        | Get transaction by ID              |
| GET    | `/transactions/<id>/results` | Admin, Agent     | View fraud prediction results      |

---

## Testing with Postman

### 1. Login

```http
POST /auth/login
```

```json
{
  "username": "admin",
  "password": "adminpass"
}
```

### 2. Create a User (Admin Only)

```http
POST /auth/create_user
Authorization: <token>
```

```json
{
  "username": "agent1",
  "password": "agentpass1",
  "role": "agent"
}
```

### 3. Create a Transaction (Agent or Admin)

```http
POST /transactions
Authorization: <token>
```

```json
{
  "customer": "Alice",
  "timestamp": "2025-04-22T15:00:00Z",
  "vendor_id": "VEND123",
  "amount": 149.95
}
```
---

## Logging

All requests and responses include:

- Source IP and Destination (host)
- Headers
- Metadata (JSON body, if any)
- Status codes and response headers

> This is printed in the container logs (Flask logger output).

---

## Project Structure

```
FDS/
├── auth_service/
│   ├── auth_main.py
│   ├── Dockerfile
│   └── requirements.txt
├── transaction_service/
│   ├── transaction_main.py
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## Authors

 **Alexander Savov and Balazs Madarasi**  
 IMC Krems – SS 2025

---