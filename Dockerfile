# Simple Docker image for Google Cloud Run.
FROM python:3.11-slim

# Force Python output to stdout/stderr (shows live logs in Cloud Run)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python packages before copying app files. Docker can reuse this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run FastAPI using python -m uvicorn, binding to 0.0.0.0 and Cloud Run's $PORT
CMD exec python -m uvicorn main:app 
