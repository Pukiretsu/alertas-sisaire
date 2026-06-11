"""API FastAPI para carga manual, muestreo automático y generación de memorias."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from air_quality_alerts.config import Settings
from air_quality_alerts.domain.engine import AirQualityAlertEngine
from air_quality_alerts.ingestion.playwright_downloader import SISAIREDownloader

app = FastAPI(
    title="Air Quality Alerts Bogotá API",
    version="1.4.0",
    description=(
        "Motor de cálculo de alertas PM2.5 con carga manual CSV/Excel, "
        "descarga automática con Playwright y salida GeoJSON para mapa GIS."
    ),
)

origins = [origin.strip() for origin in Settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_DIR = Settings.OUTPUTS_DIR
DOWNLOADS_DIR = Settings.DOWNLOADS_DIR
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


class AutoSamplingRequest(BaseModel):
    """Parámetros recibidos desde la SPA para muestreo automático."""

    estaciones: list[str] = Field(default_factory=lambda: list(Settings.DEFAULT_STATION_IDS))
    contaminante: str = "PM2.5"
    fecha_inicio: date
    fecha_fin: date
    min_valid_readings_24h: int = Field(default=18, ge=1, le=24)
    headed: bool = False


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """Healthcheck simple para pruebas locales y despliegues."""

    return {"status": "ok", "service": "air-quality-alerts-api"}


@app.get("/api/stations/catalog", tags=["stations"])
def stations_catalog() -> JSONResponse:
    """Devuelve el catálogo completo de estaciones CAR/SISAIRE como GeoJSON."""

    engine = AirQualityAlertEngine()
    return JSONResponse(engine.station_catalog_geojson())


@app.post("/api/calculate", tags=["calculation"])
async def calculate_air_quality(
    file: UploadFile = File(...),
    pollutant: str = Form("PM2.5"),
    min_valid_readings_24h: int = Form(18),
) -> JSONResponse:
    """Recibe CSV/Excel, calcula memoria y retorna resumen + URLs de descarga."""

    suffix = Path(file.filename or "input.csv").suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Solo se permiten archivos CSV, XLSX o XLS.")

    if min_valid_readings_24h < 1 or min_valid_readings_24h > 24:
        raise HTTPException(status_code=400, detail="min_valid_readings_24h debe estar entre 1 y 24.")

    result_id = str(uuid.uuid4())
    result_dir = OUTPUTS_DIR / result_id
    result_dir.mkdir(parents=True, exist_ok=True)

    input_path = result_dir / f"input{suffix}"

    try:
        with input_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        payload = _calculate_and_build_response(
            input_path=input_path,
            result_id=result_id,
            result_dir=result_dir,
            pollutant=pollutant,
            min_valid_readings_24h=min_valid_readings_24h,
            source="manual_upload",
        )
        return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error calculando archivo: {exc}") from exc
    finally:
        await file.close()


@app.post("/api/auto-sampling", tags=["sampling"])
def auto_sampling(request: AutoSamplingRequest) -> JSONResponse:
    """Descarga CSV con Playwright, calcula resultados y retorna mapa/resumen."""

    if request.fecha_fin < request.fecha_inicio:
        raise HTTPException(status_code=400, detail="La fecha final no puede ser menor a la fecha inicial.")

    if not request.estaciones:
        raise HTTPException(status_code=400, detail="Debes enviar al menos una estación para consultar.")

    if not Settings.JSF_TARGET_URL:
        raise HTTPException(
            status_code=400,
            detail=(
                "JSF_TARGET_URL no está configurada. Define la URL real del portal en backend/.env "
                "para usar el muestreo automático con Playwright."
            ),
        )

    result_id = str(uuid.uuid4())
    result_dir = OUTPUTS_DIR / result_id
    result_dir.mkdir(parents=True, exist_ok=True)

    try:
        downloader = SISAIREDownloader(
            ids_estaciones=request.estaciones,
            contaminante=request.contaminante,
            fecha_ini=request.fecha_inicio.isoformat(),
            fecha_fin=request.fecha_fin.isoformat(),
            ruta=result_dir,
            filename="auto_sampling_raw",
            headless=not request.headed,
        )
        downloaded_path = downloader.start_download()

        payload = _calculate_and_build_response(
            input_path=downloaded_path,
            result_id=result_id,
            result_dir=result_dir,
            pollutant=request.contaminante,
            min_valid_readings_24h=request.min_valid_readings_24h,
            source="playwright_auto_sampling",
        )
        payload["download_raw_url"] = f"/api/results/{result_id}/{downloaded_path.name}"
        payload["process_steps"] = [
            "Descarga automática desde portal JSF/SISAIRE",
            "Normalización de CSV descargado",
            "Cálculo de medias móviles 24h",
            "Seguimiento de 48 lecturas",
            "Publicación de memoria CSV, Excel y GeoJSON",
        ]
        return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error ejecutando muestreo automático: {exc}") from exc


@app.get("/api/results/{result_id}/{filename}", tags=["results"])
def download_result(result_id: str, filename: str) -> FileResponse:
    """Descarga artefactos generados por un cálculo."""

    allowed = {"memoria_calculo.csv", "memoria_calculo.xlsx", "resumen_estaciones.csv", "stations.geojson", "reporte-auto_sampling_raw.csv"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Archivo no disponible.")

    path = OUTPUTS_DIR / result_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Resultado no encontrado.")

    if filename.endswith(".geojson"):
        media_type = "application/geo+json"
    elif filename.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        media_type = "text/csv"
    return FileResponse(path, media_type=media_type, filename=filename)


def _calculate_and_build_response(
    *,
    input_path: Path,
    result_id: str,
    result_dir: Path,
    pollutant: str,
    min_valid_readings_24h: int,
    source: str,
) -> dict[str, Any]:
    output_csv_path = result_dir / "memoria_calculo.csv"
    summary_csv_path = result_dir / "resumen_estaciones.csv"
    output_xlsx_path = result_dir / "memoria_calculo.xlsx"
    geojson_path = result_dir / "stations.geojson"

    engine = AirQualityAlertEngine(
        pollutant=pollutant,
        min_valid_readings_24h=min_valid_readings_24h,
    )
    calculated = engine.run_pipeline(input_path, output_csv_path)
    summary = engine.to_station_summary(calculated)
    summary.to_csv(summary_csv_path, index=False, encoding="utf-8-sig")
    engine.export_memory_excel(calculated, output_xlsx_path)

    geojson = engine.to_geojson(calculated)
    geojson_path.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "result_id": result_id,
        "source": source,
        "rows": int(len(calculated)),
        "stations": int(summary["station_name"].nunique()) if not summary.empty else 0,
        "declared_alerts": int(calculated["declared_alert"].sum()) if "declared_alert" in calculated else 0,
        "download_csv_url": f"/api/results/{result_id}/memoria_calculo.csv",
        "download_excel_url": f"/api/results/{result_id}/memoria_calculo.xlsx",
        "download_summary_url": f"/api/results/{result_id}/resumen_estaciones.csv",
        "geojson_url": f"/api/results/{result_id}/stations.geojson",
        "station_summary": _records_for_json(summary),
        "stations_geojson": geojson,
        "process_steps": [
            "Archivo recibido",
            "Normalización de columnas",
            "Cálculo de media móvil 24h por estación",
            "Seguimiento de persistencia por 48 lecturas",
            "Generación de memoria CSV, Excel y GeoJSON",
        ],
    }


def _records_for_json(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    safe_df = df.copy()
    for column in safe_df.columns:
        if pd.api.types.is_datetime64_any_dtype(safe_df[column]):
            safe_df[column] = safe_df[column].dt.strftime("%Y-%m-%d %H:%M:%S")

    return json.loads(safe_df.to_json(orient="records", date_format="iso"))
