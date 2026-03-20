FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Production image
FROM python:3.11-slim

WORKDIR /app

# Security: Create non-root user
RUN groupadd -r resonant && useradd -r -g resonant resonant

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# Create data directory with proper permissions
RUN mkdir -p /app/data && chown -R resonant:resonant /app

# Security: Switch to non-root user
USER resonant

# Environment variables with secure defaults
ENV NODE_ENV=production \
    NODE_HOST=0.0.0.0 \
    NODE_PORT=8081 \
    NODE_LOG_LEVEL=INFO \
    NODE_WORKERS=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8081/status || exit 1

# Start the node API server
CMD ["python", "-m", "resonant_node.api"]
