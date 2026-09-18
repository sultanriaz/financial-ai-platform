# backend/Dockerfile
# FIX #11: provides an image for all three Python services (API, scraper, consumer).
# docker-compose overrides CMD per service; PYTHONPATH is set so all imports resolve.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

ENV PYTHONPATH=/app

# Default entrypoint — overridden per service in docker-compose.yml
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
