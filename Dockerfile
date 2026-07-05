# ─── STAGE 1: Builder ──────────────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /build

# Build-time dependencies (kuch pip packages compile karne ke liye chahiye)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Pehle requirements copy karo (Docker layer caching ke liye)
COPY app/requirements.txt .

RUN pip install --user --no-cache-dir -r requirements.txt

# ─── STAGE 2: Runner (Final Production Image) ──────────────
FROM python:3.10-slim AS runner

# curl install karo — HEALTHCHECK ke liye chahiye
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user banao — security best practice
RUN useradd --create-home appuser
WORKDIR /home/appuser

# Builder stage se sirf installed Python packages copy karo
COPY --from=builder /root/.local /home/appuser/.local

# Application code copy karo
COPY app/ .
COPY frontend/ ./frontend/

# Ownership fix karo
RUN chown -R appuser:appuser /home/appuser

USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/home/appuser/.local/lib/python3.10/site-packages

EXPOSE 8000

# Docker-level health check (K8s probes ke alawa extra safety layer)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
