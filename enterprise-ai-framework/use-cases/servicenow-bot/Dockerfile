FROM python:3.10-slim

# Build arguments
ARG BUILD_SHA=unknown
ARG BUILD_DATE=unknown
ARG USE_CASE=servicenow-bot

# Labels
LABEL org.opencontainers.image.revision=$BUILD_SHA
LABEL org.opencontainers.image.created=$BUILD_DATE
LABEL org.opencontainers.image.title="Enterprise Agent - ServiceNow Bot"

WORKDIR /app

# Copy and install patterns core first (layer caching)
COPY ai-patterns-core /app/ai-patterns-core
RUN pip install --no-cache-dir /app/ai-patterns-core

# Copy use-case specific files
COPY use-cases/servicenow-bot/main.py /app/main.py
COPY use-cases/servicenow-bot/agent.yaml /app/agent.yaml

# Install runtime dependencies
RUN pip install --no-cache-dir uvicorn[standard]>=0.23.0

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check using Python (curl not available in slim image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
