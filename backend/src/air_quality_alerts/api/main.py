"""API FastAPI para carga manual, muestreo automático y sesiones con progreso."""

from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from air_quality_alerts.config import Settings
from air_quality_alerts.domain.engine import AirQualityAlertEngine
from air_quality_alerts.ingestion.playwright_downloader import SISAIREDownloader
from air_quality_alerts.storage import JobRepository

app = FastAPI(
    title="Air Quality Alerts Bogotá API",
    version="2.0.0",
    description=(
        "Motor de cálculo de alertas PM2.5 con carga manual CSV/Excel, "
        "descarga automática por estación, sesiones persistentes y salida GeoJSON."
    ),
)

origins = [origin.strip() for origin in Settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
allow_credentials = "*" not in origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_DIR = Settings.OUTPUTS_DIR
DOWNLOADS_DIR = Settings.DOWNLOADS_DIR
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

jobs = JobRepository()
ProgressReporter = Callable[[str, float, str], None]


class AutoSamplingRequest(BaseModel):
    """Parámetros recibidos desde la SPA para muestreo automático."""

    estaciones: list[str] = Field(default_factory=lambda: list(Settings.DEFAULT_STATION_IDS))
    contaminante: str = "PM2.5"
    fecha_inicio: date
    fecha_fin: date
    min_valid_readings_24h: int = Field(default=18, ge=1, le=24)
    headed: bool = False
    download_all_registered: bool = False
    continue_on_error: bool = True


@app.on_event("startup")
def startup() -> None:
    """Inicializa la base de datos de sesiones al arrancar el contenedor."""

    jobs.init_schema()


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """Healthcheck simple para pruebas locales, ALB y despliegues."""

    return {"status": "ok", "service": "air-quality-alerts-api", "version": "2.0.0"}


@app.get("/api/stations/catalog", tags=["stations"])
def stations_catalog() -> JSONResponse:
    """Devuelve el catálogo completo de estaciones CAR/SISAIRE como GeoJSON."""

    engine = AirQualityAlertEngine()
    return JSONResponse(engine.station_catalog_geojson())


@app.get("/api/stations", tags=["stations"])
def stations_list() -> JSONResponse:
    """Devuelve el catálogo de estaciones como lista para formularios y automatizaciones."""

    catalog = _load_registered_stations()
    return JSONResponse({"count": len(catalog), "stations": catalog})


@app.get("/api/jobs", tags=["jobs"])
def list_jobs(limit: int = 25) -> JSONResponse:
    """Lista las últimas sesiones de cálculo o descarga."""

    return JSONResponse({"jobs": jobs.list_jobs(limit=limit)})


@app.get("/api/jobs/{job_id}", tags=["jobs"])
def get_job(job_id: str) -> JSONResponse:
    """Consulta el estado, progreso, eventos y resultado de una sesión."""

    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    return JSONResponse(job)


@app.post("/api/jobs/calculate", status_code=status.HTTP_202_ACCEPTED, tags=["jobs"])
async def create_calculation_job(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(...)],
    pollutant: Annotated[str, Form()] = "PM2.5",
    min_valid_readings_24h: Annotated[int, Form()] = 18,
) -> JSONResponse:
    """Crea una sesión asíncrona para cargar archivo y calcular memoria."""

    suffix = Path(file.filename or "input.csv").suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Solo se permiten archivos CSV, XLSX o XLS.")
    if min_valid_readings_24h < 1 or min_valid_readings_24h > 24:
        raise HTTPException(status_code=400, detail="min_valid_readings_24h debe estar entre 1 y 24.")

    job_id = str(uuid.uuid4())
    result_dir = OUTPUTS_DIR / job_id
    result_dir.mkdir(parents=True, exist_ok=True)
    input_path = result_dir / f"input{suffix}"

    try:
        with input_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        await file.close()

    job = jobs.create_job(
        job_id=job_id,
        kind="manual_upload",
        request_payload={
            "filename": file.filename,
            "pollutant": pollutant,
            "min_valid_readings_24h": min_valid_readings_24h,
        },
    )
    background_tasks.add_task(
        _run_manual_job,
        job_id,
        input_path,
        result_dir,
        pollutant,
        min_valid_readings_24h,
    )
    return JSONResponse(job, status_code=status.HTTP_202_ACCEPTED)


@app.post("/api/jobs/auto-sampling", status_code=status.HTTP_202_ACCEPTED, tags=["jobs"])
def create_auto_sampling_job(request: AutoSamplingRequest, background_tasks: BackgroundTasks) -> JSONResponse:
    """Crea una sesión asíncrona para descargar estación por estación y calcular."""

    _validate_auto_sampling_request(request)
    job_id = str(uuid.uuid4())
    result_dir = OUTPUTS_DIR / job_id
    result_dir.mkdir(parents=True, exist_ok=True)

    request_payload = _model_to_json_dict(request)
    job = jobs.create_job(job_id=job_id, kind="auto_sampling", request_payload=request_payload)
    background_tasks.add_task(_run_auto_sampling_job, job_id, request_payload, result_dir)
    return JSONResponse(job, status_code=status.HTTP_202_ACCEPTED)


@app.post("/api/calculate", tags=["calculation"])
async def calculate_air_quality(
    file: Annotated[UploadFile, File(...)],
    pollutant: Annotated[str, Form()] = "PM2.5",
    min_valid_readings_24h: Annotated[int, Form()] = 18,
) -> JSONResponse:
    """Endpoint síncrono conservado para compatibilidad con clientes existentes."""

    suffix = Path(file.filename or "input.csv").suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Solo se permiten archivos CSV, XLSX o XLS.")

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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error calculando archivo: {exc}") from exc
    finally:
        await file.close()


@app.post("/api/auto-sampling", tags=["sampling"])
def auto_sampling(request: AutoSamplingRequest) -> JSONResponse:
    """Endpoint síncrono conservado para ejecutar descarga y cálculo en una sola respuesta."""

    _validate_auto_sampling_request(request)
    result_id = str(uuid.uuid4())
    result_dir = OUTPUTS_DIR / result_id
    result_dir.mkdir(parents=True, exist_ok=True)
    payload = _download_by_station_and_calculate(
        request_payload=_model_to_json_dict(request),
        result_id=result_id,
        result_dir=result_dir,
    )
    return JSONResponse(payload)


@app.get("/api/results/{result_id}/{filename}", tags=["results"])
def download_result(result_id: str, filename: str) -> FileResponse:
    """Descarga artefactos generados por una sesión."""

    safe_filename = Path(filename).name
    if safe_filename != filename or not _is_allowed_result_filename(safe_filename):
        raise HTTPException(status_code=404, detail="Archivo no disponible.")

    path = OUTPUTS_DIR / result_id / safe_filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Resultado no encontrado.")

    if safe_filename.endswith(".geojson"):
        media_type = "application/geo+json"
    elif safe_filename.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        media_type = "text/csv"
    return FileResponse(path, media_type=media_type, filename=safe_filename)


def _run_manual_job(
    job_id: str,
    input_path: Path,
    result_dir: Path,
    pollutant: str,
    min_valid_readings_24h: int,
) -> None:
    def report(message: str, progress: float, step: str) -> None:
        jobs.update_job(job_id, status="running", progress=progress, current_step=step, message=message)

    try:
        report("Archivo recibido y guardado en la sesión.", 8, "Preparación")
        payload = _calculate_and_build_response(
            input_path=input_path,
            result_id=job_id,
            result_dir=result_dir,
            pollutant=pollutant,
            min_valid_readings_24h=min_valid_readings_24h,
            source="manual_upload",
            report=report,
        )
        jobs.update_job(
            job_id,
            status="completed",
            progress=100,
            current_step="Finalizado",
            message="Memorias y GeoJSON generados correctamente.",
            result_payload=payload,
            completed=True,
        )
    except Exception as exc:  # pragma: no cover - flujo operativo
        jobs.update_job(
            job_id,
            status="failed",
            progress=100,
            current_step="Error",
            message="No fue posible completar el cálculo.",
            error=str(exc),
            completed=True,
        )


def _run_auto_sampling_job(job_id: str, request_payload: dict[str, Any], result_dir: Path) -> None:
    def report(message: str, progress: float, step: str) -> None:
        jobs.update_job(job_id, status="running", progress=progress, current_step=step, message=message)

    try:
        report("Iniciando descarga automática por estación.", 3, "Preparación")
        payload = _download_by_station_and_calculate(
            request_payload=request_payload,
            result_id=job_id,
            result_dir=result_dir,
            report=report,
        )
        jobs.update_job(
            job_id,
            status="completed",
            progress=100,
            current_step="Finalizado",
            message="Descarga por estación, cálculo y publicación de artefactos completados.",
            result_payload=payload,
            completed=True,
        )
    except Exception as exc:  # pragma: no cover - flujo operativo
        jobs.update_job(
            job_id,
            status="failed",
            progress=100,
            current_step="Error",
            message="No fue posible completar el muestreo automático.",
            error=str(exc),
            completed=True,
        )


def _download_by_station_and_calculate(
    *,
    request_payload: dict[str, Any],
    result_id: str,
    result_dir: Path,
    report: ProgressReporter | None = None,
) -> dict[str, Any]:
    stations = _resolve_requested_stations(request_payload)
    contaminante = request_payload.get("contaminante") or "PM2.5"
    continue_on_error = bool(request_payload.get("continue_on_error", True))
    headed = bool(request_payload.get("headed", False))

    downloaded_paths: list[Path] = []
    station_downloads: list[dict[str, Any]] = []
    total = len(stations)

    for index, station_id in enumerate(stations, start=1):
        progress = 5 + ((index - 1) / max(total, 1)) * 45
        _emit(report, f"Descargando estación {index}/{total}: {station_id}", progress, "Descarga automática")
        try:
            downloader = SISAIREDownloader(
                ids_estaciones=[station_id],
                contaminante=contaminante,
                fecha_ini=str(request_payload["fecha_inicio"]),
                fecha_fin=str(request_payload["fecha_fin"]),
                ruta=result_dir,
                filename=f"station_{station_id}",
                headless=not headed,
            )
            downloaded_path = downloader.start_download()
            downloaded_paths.append(downloaded_path)
            station_downloads.append({"station_id": station_id, "status": "downloaded", "file": downloaded_path.name})
            _emit(report, f"Estación {station_id} descargada correctamente.", 5 + (index / total) * 45, "Descarga automática")
        except Exception as exc:  # pragma: no cover - requiere portal real
            station_downloads.append({"station_id": station_id, "status": "failed", "error": str(exc)})
            if not continue_on_error:
                raise
            _emit(report, f"Estación {station_id} no descargó. Se continúa con las demás.", 5 + (index / total) * 45, "Descarga automática")

    if not downloaded_paths:
        raise RuntimeError("No se pudo descargar información de ninguna estación.")

    _emit(report, "Unificando CSV descargados por estación.", 54, "Consolidación")
    combined_path = _combine_downloaded_files(downloaded_paths, result_dir / "auto_sampling_raw.csv")

    payload = _calculate_and_build_response(
        input_path=combined_path,
        result_id=result_id,
        result_dir=result_dir,
        pollutant=contaminante,
        min_valid_readings_24h=int(request_payload.get("min_valid_readings_24h") or 18),
        source="playwright_auto_sampling_by_station",
        report=report,
    )
    payload["download_raw_url"] = f"/api/results/{result_id}/{combined_path.name}"
    payload["station_downloads"] = station_downloads
    payload["downloaded_station_count"] = len(downloaded_paths)
    payload["requested_station_count"] = total
    payload["process_steps"] = [
        "Creación de sesión persistente",
        "Descarga automática individual por estación registrada",
        "Consolidación de CSV descargados",
        "Normalización y cálculo de medias móviles 24h",
        "Seguimiento de 48 lecturas: declaratoria, finalización y recategorización",
        "Publicación de memoria CSV, Excel, resumen y GeoJSON",
    ]
    return payload


def _calculate_and_build_response(
    *,
    input_path: Path,
    result_id: str,
    result_dir: Path,
    pollutant: str,
    min_valid_readings_24h: int,
    source: str,
    report: ProgressReporter | None = None,
) -> dict[str, Any]:
    output_csv_path = result_dir / "memoria_calculo.csv"
    summary_csv_path = result_dir / "resumen_estaciones.csv"
    output_xlsx_path = result_dir / "memoria_calculo.xlsx"
    geojson_path = result_dir / "stations.geojson"

    engine = AirQualityAlertEngine(
        pollutant=pollutant,
        min_valid_readings_24h=min_valid_readings_24h,
    )

    _emit(report, "Leyendo archivo fuente.", 58, "Lectura")
    raw_df = engine.read_file(input_path)
    _emit(report, "Normalizando columnas, fechas, contaminante y coordenadas.", 66, "Normalización")
    normalized_df = engine.normalize(raw_df)
    _emit(report, "Calculando media móvil 24h, umbrales y seguimiento de persistencia.", 78, "Cálculo")
    calculated = engine.calculate(normalized_df)

    _emit(report, "Exportando memoria CSV.", 86, "Exportación")
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    calculated.to_csv(output_csv_path, index=False, encoding="utf-8-sig")

    summary = engine.to_station_summary(calculated)
    summary.to_csv(summary_csv_path, index=False, encoding="utf-8-sig")

    _emit(report, "Generando memoria Excel con resumen, parámetros y diccionario.", 92, "Exportación")
    engine.export_memory_excel(calculated, output_xlsx_path)

    _emit(report, "Generando GeoJSON para mapa.", 96, "Publicación")
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


def _model_to_json_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def _validate_auto_sampling_request(request: AutoSamplingRequest) -> None:
    if request.fecha_fin < request.fecha_inicio:
        raise HTTPException(status_code=400, detail="La fecha final no puede ser menor a la fecha inicial.")
    if not request.download_all_registered and not request.estaciones:
        raise HTTPException(status_code=400, detail="Debes enviar al menos una estación para consultar.")
    if not Settings.JSF_TARGET_URL:
        raise HTTPException(
            status_code=400,
            detail=(
                "JSF_TARGET_URL no está configurada. Define la URL real del portal en backend/.env "
                "o en las variables del contenedor para usar el muestreo automático con Playwright."
            ),
        )


def _resolve_requested_stations(request_payload: dict[str, Any]) -> list[str]:
    if request_payload.get("download_all_registered"):
        stations = [station["station_id"] for station in _load_registered_stations()]
    else:
        stations = [str(item).strip() for item in request_payload.get("estaciones", []) if str(item).strip()]
    if not stations:
        raise ValueError("No hay estaciones disponibles para descargar.")
    # Evita descargas repetidas si el usuario duplica IDs en el textarea.
    return list(dict.fromkeys(stations))


def _load_registered_stations() -> list[dict[str, Any]]:
    engine = AirQualityAlertEngine()
    catalog = engine._load_station_catalog()  # noqa: SLF001 - reutiliza normalización del motor.
    if catalog.empty:
        return []
    renamed = catalog.rename(
        columns={
            "catalog_station_id": "station_id",
            "catalog_station_name": "station_name",
            "catalog_latitude": "latitude",
            "catalog_longitude": "longitude",
            "catalog_altitude": "altitude",
        }
    )
    columns = ["station_id", "station_name", "latitude", "longitude", "altitude"]
    existing_columns = [column for column in columns if column in renamed.columns]
    result = renamed[existing_columns].copy()
    result["station_id"] = result["station_id"].astype(str)
    return _records_for_json(result)


def _combine_downloaded_files(downloaded_paths: list[Path], output_path: Path) -> Path:
    engine = AirQualityAlertEngine()
    frames = []
    for path in downloaded_paths:
        frame = engine.read_file(path)
        frame["source_download_file"] = path.name
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def _is_allowed_result_filename(filename: str) -> bool:
    allowed = {
        "memoria_calculo.csv",
        "memoria_calculo.xlsx",
        "resumen_estaciones.csv",
        "stations.geojson",
        "auto_sampling_raw.csv",
        "reporte-auto_sampling_raw.csv",
    }
    return filename in allowed or (filename.startswith("reporte-station_") and filename.endswith(".csv"))


def _emit(report: ProgressReporter | None, message: str, progress: float, step: str) -> None:
    if report:
        report(message, progress, step)


def _records_for_json(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    safe_df = df.copy()
    for column in safe_df.columns:
        if pd.api.types.is_datetime64_any_dtype(safe_df[column]):
            safe_df[column] = safe_df[column].dt.strftime("%Y-%m-%d %H:%M:%S")
    return json.loads(safe_df.to_json(orient="records", date_format="iso"))
