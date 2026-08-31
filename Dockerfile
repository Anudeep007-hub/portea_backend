# Simple Docker image for Google Cloud Run.
FROM python:3.11-slim

WORKDIR /app

# Install Python packages before copying app files. Docker can reuse this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn main:app"]
