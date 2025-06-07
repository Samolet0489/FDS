# Base image that matches the pickle’s Python version
FROM python:3.10

# OS-level MPI + build tools (no python3-mpi4py package needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        openmpi-bin \
        libopenmpi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Make pip modern so it finds wheels
RUN pip install --upgrade pip setuptools wheel

# Python deps — pin mpi4py to a version that has a wheel
# NO compile step, so the build is quick and small
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy model & service code
COPY fraud_rf_model.pkl mpi_service.py ./

# Start with 5 MPI ranks
CMD ["mpiexec", "--allow-run-as-root", "-n", "5", "python", "mpi_service.py"]