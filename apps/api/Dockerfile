# Build context is the repo root (see infra/docker-compose.yml) because this
# image needs apps/api + the committed data/kyiv_extract + scripts/seed_db.py,
# preserving the same relative layout the code expects locally.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt

COPY apps/api apps/api
COPY data data
COPY scripts scripts
COPY infra/api-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace/apps/api
ENV PYTHONPATH=/workspace/apps/api \
    PYTHONUNBUFFERED=1

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
