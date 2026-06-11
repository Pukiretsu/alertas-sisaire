# Backend - Air Quality Alerts Bogotá

Backend Python/FastAPI para descarga, cálculo y exposición de resultados del motor de alertas PM2.5.

## Comandos rápidos

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

```bash
air-quality-alerts api
```

```bash
air-quality-alerts calculate --input ../data/samples/ejemplo_pm25_bogota.csv --output ../outputs/memoria_demo.csv
```

Ejemplo con reporte horario real de SISAIRE:

```bash
air-quality-alerts calculate \
  --input ../data/samples/reporte_sisaire_pm25_horario.csv \
  --output ../outputs/memoria_reporte_sisaire_pm25_horario.csv \
  --excel-output ../outputs/memoria_reporte_sisaire_pm25_horario.xlsx
```

## Endpoints

- `POST /api/calculate`: carga manual de CSV/XLSX/XLS.
- `POST /api/auto-sampling`: descarga con Playwright + cálculo.
- `GET /api/results/{result_id}/{filename}`: descarga de artefactos generados.

Consulta la documentación completa en el README de la raíz del repositorio.
