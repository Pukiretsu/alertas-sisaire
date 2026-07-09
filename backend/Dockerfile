FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    OUTPUTS_DIR=/app/outputs \
    DOWNLOADS_DIR=/app/downloads \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install -e .

RUN mkdir -p /app/outputs /app/downloads \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app /ms-playwright

USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["air-quality-alerts", "api", "--host", "0.0.0.0", "--port", "8000"]
