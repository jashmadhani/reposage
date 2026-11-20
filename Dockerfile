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

# Run as a non-root user and clone repositories under /tmp, the one place
# every host lets us write.
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 CLONE_DIR=/tmp/reposage_clone
# Cloud Run sets PORT. The index lives in memory, so run a single worker.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
