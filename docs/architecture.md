# Arquitectura técnica

## Flujo de extremo a extremo

```text
                    ┌──────────────────────────────┐
                    │ SPA React + Vite + Tailwind   │
                    │ frontend/src + frontend/dist  │
                    └──────────────┬───────────────┘
                                   │
                 ┌─────────────────┴─────────────────┐
                 │                                   │
                 ▼                                   ▼
       Carga manual CSV/XLSX              Muestreo automático
                 │                         con Playwright
                 │                                   │
                 ▼                                   ▼
          POST /api/calculate              POST /api/auto-sampling
                 │                                   │
                 │                         Portal JSF/SISAIRE
                 │                                   │
                 │                         CSV descargado
                 └─────────────────┬─────────────────┘
                                   ▼
                        AirQualityAlertEngine
                 ┌─────────────────┼─────────────────┐
                 ▼                 ▼                 ▼
       Normalización       Media móvil 24h    Monitoreo 48 lecturas
                 │                 │                 │
                 └─────────────────┴─────────────────┘
                                   ▼
              Persistencia > 75% y clasificación PM2.5
                                   │
                 ┌─────────────────┼─────────────────┐
                 ▼                 ▼                 ▼
       memoria_calculo.csv  resumen_estaciones.csv  stations.geojson
                                   │
                                   ▼
                     Mapa Leaflet + tabla de estaciones
```

## Componentes

### 1. SPA web

`frontend/src/`

Aplicación React de una sola vista. En la parte superior permite elegir entre carga manual y muestreo automático. Mientras la API procesa, muestra el avance lógico del cálculo. Al finalizar, permite descargar memorias de cálculo y actualiza el mapa GIS con el GeoJSON generado por el backend.

El build estático queda en `frontend/dist` y puede desplegarse en un hosting estático, S3, Nginx o similar.

### 2. Ingesta automática

`backend/src/air_quality_alerts/ingestion/playwright_downloader.py`

Automatiza el portal JSF/SISAIRE con Playwright, selecciona estaciones, contaminante, fechas, granularidad horaria y descarga un CSV. Los selectores están aislados para facilitar ajustes cuando el portal cambie.

### 3. Dominio / cálculo

`backend/src/air_quality_alerts/domain/engine.py`

Contiene la lógica central del proyecto. No depende de la API ni del frontend, por lo que puede usarse desde CLI, jobs programados, pruebas o servicios web.

Reglas principales:

- Agrupa lecturas por estación.
- Calcula media móvil de 24 horas.
- Clasifica PM2.5 en Normal, Prevención, Alerta y Emergencia.
- Si se detecta superación, inicia seguimiento de 48 lecturas.
- Declara alerta si más del 75% de las lecturas monitoreadas superan el umbral.

### 4. API

`backend/src/air_quality_alerts/api/main.py`

Endpoints principales:

- `POST /api/calculate`: recibe CSV/XLSX/XLS manual.
- `POST /api/auto-sampling`: descarga datos con Playwright y calcula resultados.
- `GET /api/results/{result_id}/{filename}`: descarga memoria, resumen, GeoJSON o CSV fuente.

### 5. Visualización GIS

`frontend/src/components/BogotaMap.jsx`

Usa Leaflet + OpenStreetMap para visualizar estaciones como puntos GeoJSON. Cada punto muestra estado actual, medición, media móvil de 24 horas y fecha de lectura.

## Despliegue sugerido

- Backend: contenedor Docker, VM, ECS, Cloud Run, App Service o similar.
- Frontend: `frontend/dist` en hosting estático.
- Archivos generados: volumen local o bucket de objetos.
- Descarga automática: endpoint bajo demanda o job programado.

## Escalabilidad futura

- Persistir resultados históricos en base de datos.
- Agendar descarga automática con cron, Airflow, Celery Beat o EventBridge.
- Parametrizar umbrales por contaminante desde base de datos.
- Agregar autenticación para perfiles técnico/operativo.
- Publicar resultados como API pública GeoJSON.
