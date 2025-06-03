FROM python:3.8

# 1) Install OS-level MPI + build tools (for mpi4py to link against)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      openmpi-bin \
      libopenmpi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Upgrade pip/setuptools/wheel so pip can fetch the binary mpi4py wheel
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir mpi4py
# 3) Copy and install all Python dependencies (including mpi4py)
#    Your requirements.txt must list “mpi4py” as the first line.
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 4) Copy your service code + model
COPY mpi_service.py fraud_rf_model.pkl /app/

# 5) On startup, launch MPI under root-override with 5 ranks
CMD ["bash", "-lc", "mpiexec --allow-run-as-root -n 5 python mpi_service.py"]