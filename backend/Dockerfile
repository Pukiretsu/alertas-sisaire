FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY src ./src

RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["air-quality-alerts", "api", "--host", "0.0.0.0", "--port", "8000"]
