# Air Quality Alerts Bogotá

Proyecto de portafolio para automatizar la descarga de datos de calidad del aire, calcular alertas PM2.5 y visualizar estaciones en un mapa tipo GIS de Bogotá.

La solución combina un backend Python con FastAPI, un motor de cálculo basado en Pandas, descarga automática con Playwright y una SPA en React construida con Vite + Tailwind. El repositorio incluye además `frontend/dist`, listo para publicar como sitio estático.

## Funcionalidades principales

- Descarga automática de CSV desde un portal JSF/SISAIRE usando Playwright.
- Motor de cálculo compatible con CSV, XLSX y XLS.
- Normalización de columnas para formatos tipo SISAIRE, reportes horarios, reportes diarios y formatos manuales.
- Cálculo de media móvil real de 24 horas por estación para reportes horarios, con soporte para reportes diarios SISAIRE ya preagregados.
- Monitoreo de 48 lecturas posteriores cuando se detecta superación de umbral.
- Declaración de alerta cuando más del 75% de las lecturas monitoreadas superan el umbral.
- API FastAPI para carga manual, catálogo de estaciones, muestreo automático y descarga de resultados.
- SPA React/Vite/Tailwind con experiencia tipo dashboard: modales, drag-and-drop, confirmaciones, mapa GIS interactivo y tabla filtrable.
- Build estático generado en `frontend/dist` para despliegue rápido.
- Catálogo GeoJSON de estaciones CAR/SISAIRE generado desde `SisaireCompletoCAR.csv`.
- Memoria de cálculo en CSV y Excel (`.xlsx`).

## Reglas de negocio PM2.5

| Estado | Rango PM2.5 |
|---|---:|
| Normal | Menor a 38 |
| Prevención | 38 - 55 |
| Alerta | 56 - 150 |
| Emergencia | Mayor o igual a 151 |

La ventana de 24 horas requiere, por defecto, mínimo 18 lecturas válidas para evitar decisiones con datos incompletos. Este parámetro se puede ajustar por CLI, API o desde la app web.

## Arquitectura del repositorio

```text
air-quality-alerts-bogota/
├── backend/
│   ├── src/air_quality_alerts/
│   │   ├── api/                  # FastAPI: carga manual, muestreo automático y descargas
│   │   ├── domain/               # Motor de cálculo de alertas
│   │   ├── ingestion/            # Scraper/descargador Playwright
│   │   ├── cli.py                # Comandos de consola
│   │   └── config.py             # Settings por variables de entorno
│   ├── tests/                    # Pruebas unitarias del motor
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/                      # SPA React + Tailwind
│   ├── public/                   # GeoJSON de estaciones CAR/SISAIRE
│   ├── dist/                     # Build estático listo para publicar
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── data/
│   ├── catalog/                  # Catálogo único de estaciones con coordenadas
│   ├── samples/                  # Datos livianos para demo y reporte SISAIRE
│   ├── raw/                      # Descargas reales no versionadas
│   └── processed/                # Datos procesados no versionados
├── docs/                         # Documentación técnica
├── outputs/                      # Memorias generadas no versionadas
├── downloads/                    # CSV descargados no versionados
└── Makefile                      # Comandos rápidos de desarrollo
```

## Requisitos

- Python 3.11 recomendado.
- Node.js 18 o superior.
- Playwright Chromium para la descarga automática.

## Instalación backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env
```

## Ejecutar cálculo de demo

Desde la carpeta `backend`:

```bash
air-quality-alerts calculate \
  --input ../data/samples/ejemplo_pm25_bogota.csv \
  --output ../outputs/memoria_demo.csv \
  --excel-output ../outputs/memoria_demo.xlsx
```

O desde la raíz:

```bash
make calculate-demo
```

## Levantar API

```bash
cd backend
air-quality-alerts api
```

Healthcheck:

```text
GET http://localhost:8000/api/health
```

Endpoints principales:

```text
GET  http://localhost:8000/api/stations/catalog
POST http://localhost:8000/api/calculate
POST http://localhost:8000/api/auto-sampling
GET  http://localhost:8000/api/results/{result_id}/{filename}
```

### Carga manual

`POST /api/calculate` recibe `multipart/form-data`:

- `file`: archivo CSV, XLSX o XLS.
- `pollutant`: por defecto `PM2.5`.
- `min_valid_readings_24h`: por defecto `18`.

### Muestreo automático

`POST /api/auto-sampling` recibe JSON:

```json
{
  "estaciones": ["29586", "31877", "8249"],
  "contaminante": "PM2.5",
  "fecha_inicio": "2026-01-01",
  "fecha_fin": "2026-01-03",
  "min_valid_readings_24h": 18,
  "headed": false
}
```

Para usar este flujo debes configurar `JSF_TARGET_URL` en `backend/.env` con la URL real del portal.

## Ejecutar frontend en desarrollo

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Abrir:

```text
http://localhost:5173
```

La SPA permite:

1. Subir archivos CSV/Excel de forma manual con drag-and-drop.
2. Ver el estado del proceso paso a paso con barra de progreso.
3. Abrir modales de ayuda, confirmación de muestreo y resultados generados.
4. Descargar memoria de cálculo en CSV/Excel, resumen por estación y GeoJSON.
5. Activar muestreo automático con Playwright para descargar datos desde el portal.
6. Poblar el mapa GIS con los resultados calculados.
7. Filtrar la tabla por estación, ID o tier y abrir detalle por estación.

## Generar y previsualizar `dist`

```bash
cd frontend
npm install
npm run build
npm run preview
```

El build queda en:

```text
frontend/dist
```

En esta entrega la carpeta `dist` ya está incluida para que puedas publicarla directamente en un hosting estático. Para usarla contra tu API local, levanta el backend en `http://localhost:8000` y abre el build con:

```bash
cd frontend
npm run preview
```

## Descarga automática con Playwright por CLI

Configura la URL real del portal en `backend/.env`:

```env
JSF_TARGET_URL=https://url-del-portal-jsf
```

Ejemplo:

```bash
cd backend
air-quality-alerts download \
  --fecha-inicio 2026-01-01 \
  --fecha-fin 2026-01-03 \
  --contaminante PM2.5 \
  --estaciones 29586 31877 8249 \
  --filename consulta_pm25
```

El CSV se guarda en `downloads/`. Los selectores Playwright están aislados en `backend/src/air_quality_alerts/ingestion/playwright_downloader.py` para que puedan ajustarse fácilmente si el portal cambia.

## Pruebas

```bash
cd backend
PYTHONPATH=src pytest
```

O desde la raíz:

```bash
make backend-test
```

## Contrato mínimo de datos

El motor intenta normalizar diferentes nombres de columnas. Para archivos manuales se recomienda usar:

| Columna | Descripción |
|---|---|
| `Estacion` | Nombre de la estación |
| `Fecha inicial` | Fecha/hora de la lectura |
| `PM2.5` | Medición del contaminante |
| `LATITUD` | Coordenada opcional para mapa |
| `LONGITUD` | Coordenada opcional para mapa |

También soporta columnas tipo SISAIRE como `NOMBRE_EST`, `MSFL_CODE`, `MED_CONCENTRACION_ESTANDAR`, `FECHA_INICIO`, `FECHA_FINAL`, `LATITUD` y `LONGITUD`. Cuando el reporte viene como `Estacion, Fecha inicial, Fecha final, PM2.5`, el motor detecta si corresponde a reporte horario o diario y enriquece coordenadas desde `data/catalog/stations_sisaire_car.csv`.


## Formatos SISAIRE soportados

### Reporte horario

El archivo `data/samples/reporte_sisaire_pm25_horario.csv` representa el formato horario recibido desde SISAIRE:

```csv
"Estacion","Fecha inicial","Fecha final","PM2.5"
"CAJICA - UMNG","2026-05-30 10:00","2026-05-30 10:59","7.21"
```

Cuando `Fecha inicial` trae hora y `Fecha final` cierra la hora, el motor lo marca como `input_granularity=hourly` y `source_format=sisaire_hourly_report`. En este caso calcula `rolling_avg_24h` como media móvil real de las últimas 24 horas por estación y deja `reading_interval_minutes=60` para trazabilidad.

Ejemplo:

```bash
cd backend
air-quality-alerts calculate \
  --input ../data/samples/reporte_sisaire_pm25_horario.csv \
  --output ../outputs/memoria_reporte_sisaire_pm25_horario.csv \
  --excel-output ../outputs/memoria_reporte_sisaire_pm25_horario.xlsx
```

### Reporte diario

El archivo `data/samples/reporte_sisaire_pm25.csv` representa el formato diario recibido desde SISAIRE:

```csv
"Estacion","Fecha inicial","Fecha final","PM2.5"
"CAJICA - UMNG","2026-05-30","","6.35909091"
```

Como este reporte no trae coordenadas, el motor cruza el nombre de estación contra el catálogo `data/catalog/stations_sisaire_car.csv`, generado desde `SisaireCompletoCAR.csv`. Para `CAJICA - UMNG`, por ejemplo, enriquece `station_id=31877`, `latitude=4.923668` y `longitude=-74.053345`.

Cuando las fechas vienen solo a nivel día y `Fecha final` está vacía, el valor `PM2.5` se trata como una media diaria 24h ya preagregada por SISAIRE. Esto evita invalidar el cálculo por falta de 18 lecturas horarias en reportes diarios.

## Salidas generadas

El cálculo produce:

- `memoria_calculo.csv`: resultado detallado por lectura.
- `memoria_calculo.xlsx`: libro con resumen, memoria, parámetros y diccionario de datos.
- `resumen_estaciones.csv`: último estado por estación.
- `stations.geojson`: puntos geográficos para visualización GIS.

Columnas clave de la memoria:

| Columna | Descripción |
|---|---|
| `input_granularity` | Granularidad detectada: `hourly` o `daily_24h_average` |
| `source_format` | Formato detectado: `sisaire_hourly_report`, `sisaire_daily_24h_report`, `car_long_report` o `manual_input` |
| `reading_interval_minutes` | Resolución estimada de la lectura en minutos |
| `rolling_avg_24h` | Media móvil de 24 horas o valor diario preagregado cuando el reporte SISAIRE viene diario |
| `is_complete_24h` | Indica si hay suficientes lecturas válidas |
| `tier_actual` | Normal, Prevención, Alerta o Emergencia |
| `monitoring_status` | Estado del seguimiento |
| `exceedance_ratio` | Porcentaje de persistencia sobre el umbral |
| `declared_alert` | Indica si se declaró alerta |
| `declared_tier` | Nivel de alerta declarado |
| `station_current_status` | Estado actual usado por el mapa |

## Stack

- Python 3.11
- Pandas
- Playwright
- FastAPI
- React
- Vite
- Tailwind CSS
- Leaflet + OpenStreetMap
- Pytest
