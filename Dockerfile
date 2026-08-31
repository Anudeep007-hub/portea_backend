# Simple Docker image for Google Cloud Run.
FROM python:3.11-slim

WORKDIR /app

# Install Python packages before copying app files. Docker can reuse this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects the $PORT environment variable (defaults to 8080)
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}

