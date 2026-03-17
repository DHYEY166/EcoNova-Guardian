# EcoNova Guardian – backend
# Build from project root: docker build -t econova-guardian .
# Runtime uses the EC2 IAM Role – no AWS keys in env needed.

FROM python:3.11-slim

# Non-root user for security
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Dependencies layer (cached unless requirements.txt changes)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY backend/ ./backend/

# Ensure data/ directory exists for SQLite + request counter
RUN mkdir -p data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Run from backend/ so relative imports (from config import ...) resolve
WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
