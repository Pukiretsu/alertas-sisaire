# Arquitectura técnica

## Vista lógica

```text
Usuario
  │
  ▼
React SPA ────────► FastAPI
  │                    │
  │                    ├── JobRepository SQLite/PostgreSQL
  │                    ├── Playwright Downloader por estación
  │                    ├── Motor AirQualityAlertEngine
  │                    └── Artefactos: CSV, XLSX, GeoJSON
  │
  └── Mapa Leaflet + Panel de sesiones
```

## Flujo de carga manual

1. El usuario sube CSV/XLS/XLSX desde la SPA.
2. FastAPI crea un job en estado `queued`.
3. El archivo se guarda en la carpeta de la sesión.
4. Un background task ejecuta lectura, normalización, cálculo y exportación.
5. La SPA consulta `/api/jobs/{job_id}` cada 1.5 segundos.
6. Al finalizar, el resultado se carga en mapa, tabla y panel de descargas.

## Flujo de muestreo automático

1. La SPA crea un job en `/api/jobs/auto-sampling`.
2. El backend resuelve las estaciones solicitadas o todas las registradas.
3. Playwright descarga estación por estación.
4. Los CSV descargados se consolidan en `auto_sampling_raw.csv`.
5. El motor calcula media móvil 24h, persistencia 48 lecturas y alerta declarada.
6. Se publican memoria CSV, memoria Excel, resumen y GeoJSON.

## Vista AWS

```text
CloudFront HTTPS
  ├── Default origin: S3 privado frontend
  └── /api/* origin: ALB HTTP
                    │
                    ▼
               ECS Fargate
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   RDS PostgreSQL              EFS outputs
```

## Decisiones cloud

- CloudFront enruta `/api/*` al ALB para evitar mixed content desde el navegador.
- Fargate ejecuta el backend en contenedor sin administrar servidores.
- RDS conserva sesiones y progreso.
- EFS conserva artefactos generados por cualquier tarea Fargate.
- S3 se mantiene privado mediante Origin Access Control.
