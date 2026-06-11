# Contrato de datos

## Entrada recomendada para carga manual

| Campo | Tipo | Requerido | Ejemplo |
|---|---|---:|---|
| `Estacion` | texto | Sí | Carvajal - Sevillana |
| `Fecha inicial` | fecha/hora | Sí | 2026-01-01 00:00:00 |
| `PM2.5` | número | Sí | 42.5 |
| `LATITUD` | número | No | 4.595 |
| `LONGITUD` | número | No | -74.148 |



## Formato real de reporte SISAIRE soportado

El motor también procesa el CSV descargado de SISAIRE con esta estructura:

| Campo | Tipo | Requerido | Ejemplo |
|---|---|---:|---|
| `Estacion` | texto | Sí | CAJICA - UMNG |
| `Fecha inicial` | fecha o fecha/hora | Sí | 2026-05-30 10:00 |
| `Fecha final` | fecha/hora | No | 2026-05-30 10:59 |
| `PM2.5` | número | Sí | 7.21 |

Reglas especiales para este formato:

- Si `Fecha inicial` viene con hora y `Fecha final` cierra la hora, el dato se marca como `hourly` y `source_format=sisaire_hourly_report`.
- Para reporte horario, `rolling_avg_24h` se calcula como media móvil real de las últimas 24 horas por estación.
- La columna `reading_interval_minutes` deja trazabilidad de la resolución estimada; para el reporte horario SISAIRE normalmente queda en `60`.
- Si `Fecha inicial` viene solo con fecha y `Fecha final` está vacía, el dato se marca como `daily_24h_average` y `source_format=sisaire_daily_24h_report`.
- En el reporte diario, `rolling_avg_24h` conserva el valor de `PM2.5` porque SISAIRE ya lo entrega como promedio 24h.
- Si el archivo no trae `LATITUD`/`LONGITUD`, se cruza la estación contra `data/catalog/stations_sisaire_car.csv`.
- El catálogo fue generado con coordenadas únicas por estación desde `SisaireCompletoCAR.csv`.

## Alias soportados

El motor también reconoce nombres frecuentes en datos SISAIRE:

- Estación: `NOMBRE_EST`, `Estacion`, `Estación`, `station_name`, `nombre_estacion`.
- Contaminante: `MSFL_CODE`, `contaminante`, `pollutant`, `parametro`.
- Valor: `MED_CONCENTRACION_ESTANDAR`, `PM2.5`, `PM25`, `valor`, `concentracion`.
- Fecha: `FECHA_INICIO`, `Fecha inicial`, `timestamp`, `fecha`.
- Coordenadas: `LATITUD`, `LONGITUD`, `lat`, `lon`, `lng`.

## Salida principal: memoria de cálculo

| Campo | Descripción |
|---|---|
| `station_id` | Identificador de estación, cuando está disponible |
| `station_name` | Nombre de estación |
| `pollutant` | Contaminante evaluado |
| `timestamp` | Fecha/hora de lectura |
| `input_granularity` | Granularidad detectada: `hourly` o `daily_24h_average` |
| `source_format` | Formato detectado: `sisaire_hourly_report`, `sisaire_daily_24h_report`, `car_long_report` o `manual_input` |
| `reading_interval_minutes` | Resolución estimada de la lectura en minutos |
| `value` | Valor de la medición |
| `valid_readings_24h` | Lecturas válidas dentro de la ventana móvil |
| `rolling_avg_24h` | Media móvil de 24 horas o promedio diario 24h preagregado si el reporte viene desde SISAIRE diario |
| `tier_actual` | Nivel del dato calculado |
| `alert_candidate` | Indica si inicia o participa en monitoreo |
| `monitoring_status` | Estado del monitoreo |
| `monitoring_threshold` | Umbral usado para evaluar persistencia |
| `exceedance_ratio` | Proporción de lecturas que superaron el umbral |
| `declared_alert` | Bandera de alerta declarada |
| `declared_tier` | Tier declarado |
| `station_current_status` | Estado final utilizado por el mapa |

## Respuesta JSON de API

Tanto `POST /api/calculate` como `POST /api/auto-sampling` devuelven una estructura similar:

```json
{
  "result_id": "uuid",
  "source": "manual_upload",
  "rows": 216,
  "stations": 3,
  "declared_alerts": 1,
  "download_csv_url": "/api/results/{id}/memoria_calculo.csv",
  "download_excel_url": "/api/results/{id}/memoria_calculo.xlsx",
  "download_summary_url": "/api/results/{id}/resumen_estaciones.csv",
  "geojson_url": "/api/results/{id}/stations.geojson",
  "station_summary": [],
  "stations_geojson": {
    "type": "FeatureCollection",
    "features": []
  },
  "process_steps": []
}
```

Cuando el proceso viene de Playwright, también puede incluir:

```json
{
  "download_raw_url": "/api/results/{id}/reporte-auto_sampling_raw.csv"
}
```

## GeoJSON del mapa

Cada estación se entrega como `Feature` con geometría tipo `Point`:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [-74.08, 4.65]
  },
  "properties": {
    "station_id": "BOG-DEMO-CENTRO",
    "station_name": "Estación Demo Centro",
    "pollutant": "PM2.5",
    "timestamp": "2026-01-03T23:00:00",
    "value": 42.0,
    "rolling_avg_24h": 42.0,
    "estado_actual": "Declarada - Prevención",
    "tier_actual": "Prevención"
  }
}
```
