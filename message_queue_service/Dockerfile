FROM python:3.10

# Set working directory
WORKDIR /app

# Install system dependencies if needed (none here)
# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the service code
COPY . .

# Expose service port
EXPOSE 7500

# Start the Flask application
CMD ["python", "queue_main.py"]
