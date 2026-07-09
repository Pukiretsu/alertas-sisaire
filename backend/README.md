# Backend FastAPI

Backend del proyecto Air Quality Alerts Bogotá. Incluye:

- API FastAPI.
- Motor de cálculo PM2.5 con Pandas.
- Descarga automática con Playwright.
- Sesiones/jobs persistentes con progreso y eventos.
- SQLite por defecto o PostgreSQL usando `DATABASE_URL`.

## Ejecutar local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env
air-quality-alerts api --reload
```

## Probar healthcheck

```bash
curl http://localhost:8000/api/health
```

## Endpoints de sesiones

```text
POST /api/jobs/calculate
POST /api/jobs/auto-sampling
GET  /api/jobs
GET  /api/jobs/{job_id}
```

Cada sesión guarda `status`, `progress`, `current_step`, `message`, `events`, errores y el `result_payload` final.
