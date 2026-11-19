FROM python:3.12-slim

# git is needed to clone the repositories users ask about.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1
# Cloud Run sets PORT. The index lives in memory, so run a single worker.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
