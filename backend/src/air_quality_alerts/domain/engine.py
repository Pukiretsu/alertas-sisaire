"""Motor de cálculo para alertas de calidad del aire.

El motor acepta archivos CSV o Excel y normaliza formatos reales de SISAIRE:

- Formato largo CAR/SISAIRE con `;`, `MED_CONCENTRACION_ESTANDAR`, `FECHA_INICIO`,
  `LATITUD`, `LONGITUD` y `MSFL_CODE`.
- Reporte descargado desde SISAIRE con columnas como `Estacion`, `Fecha inicial`,
  `Fecha final` y `PM2.5`, normalmente sin coordenadas.
- Archivos manuales con nombres equivalentes en español o inglés.

Después de normalizar, enriquece estaciones sin coordenadas usando el catálogo local
`data/catalog/stations_sisaire_car.csv`, calcula medias móviles de 24 horas por
estación y aplica la lógica de declaratoria, finalización y recategorización descrita
en la Resolución 2254 de 2017 para PM2.5.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[3]
DEFAULT_STATION_CATALOG = REPO_ROOT / "data" / "catalog" / "stations_sisaire_car.csv"


@dataclass(frozen=True)
class ThresholdTier:
    name: str
    lower: float
    upper: float | None
    severity: int


@dataclass
class MonitoringTrack:
    """Seguimiento horario de 48 lecturas para declaratoria o cierre."""

    track_id: str
    kind: str
    start_position: int
    start_index: int
    start_time: pd.Timestamp
    evaluation_positions: list[int]
    target_tier: str
    target_severity: int
    threshold_lower: float

    @property
    def end_position(self) -> int | None:
        if not self.evaluation_positions:
            return None
        return self.evaluation_positions[-1]


# Tabla 4 Resolución 2254 de 2017 para PM2.5, exposición 24 horas.
# Nota: el umbral >=355 corresponde a PM10, no a PM2.5.
PM25_TIERS: tuple[ThresholdTier, ...] = (
    ThresholdTier("Prevención", 38.0, 55.999999, 1),
    ThresholdTier("Alerta", 56.0, 150.999999, 2),
    ThresholdTier("Emergencia", 151.0, None, 3),
)

COLUMN_ALIASES = {
    "station_id": [
        "ESTACION_ID",
        "station_id",
        "id_estacion",
        "id estación",
        "codigo_estacion",
        "código estación",
        "codigo estación",
    ],
    "station_name": [
        "NOMBRE_EST",
        "Estacion",
        "Estación",
        "station",
        "station_name",
        "nombre_estacion",
        "nombre estación",
    ],
    "pollutant": ["MSFL_CODE", "contaminante", "pollutant", "parametro", "parámetro"],
    "value": [
        "MED_CONCENTRACION_ESTANDAR",
        "PM2.5",
        "PM25",
        "pm25",
        "PM 2.5",
        "PM_2_5",
        "valor",
        "value",
        "concentracion",
        "concentración",
        "medicion",
        "medición",
    ],
    "start_time": [
        "FECHA_INICIO",
        "Fecha inicial",
        "fecha inicial",
        "fecha_inicial",
        "timestamp",
        "fecha",
        "date",
    ],
    "end_time": ["FECHA_FINAL", "Fecha final", "fecha final", "fecha_final", "end_time"],
    "latitude": ["LATITUD", "latitud", "latitude", "lat"],
    "longitude": ["LONGITUD", "longitud", "longitude", "lon", "lng"],
    "altitude": ["ALTITUD", "altitud", "altitude"],
}

POLLUTANT_ALIASES = {
    "PM2.5": {"PM2.5", "PM25", "PM 2.5", "PM_2_5", "PM-2.5"},
    "PM10": {"PM10", "PM 10", "PM_10", "PM-10"},
}

MEMORY_COLUMNS = [
    "station_id",
    "station_name",
    "pollutant",
    "timestamp",
    "end_time",
    "input_granularity",
    "source_format",
    "reading_interval_minutes",
    "value",
    "valid_readings_24h",
    "rolling_avg_24h",
    "is_complete_24h",
    "tier_actual",
    "tier_severity",
    "threshold_lower",
    "alert_candidate",
    "monitoring_status",
    "monitoring_type",
    "monitoring_track_id",
    "monitoring_target_tier",
    "monitoring_start",
    "monitoring_end",
    "monitoring_threshold",
    "monitoring_readings_count",
    "same_range_readings_count",
    "same_range_ratio",
    "exceedance_readings_count",
    "exceedance_ratio",
    "below_lower_readings_count",
    "below_lower_ratio",
    "parallel_monitoring_count",
    "active_monitoring_ids",
    "monitoring_event",
    "declared_alert",
    "declared_tier",
    "finalized_alert",
    "recategorized_alert",
    "state_transition",
    "calculation_status",
    "station_current_status",
    "state_tier",
    "state_started_at",
    "latitude",
    "longitude",
    "altitude",
]


class AirQualityAlertEngine:
    """Calcula medias móviles, seguimientos paralelos y estados de alerta."""

    def __init__(
        self,
        pollutant: str = "PM2.5",
        tiers: Iterable[ThresholdTier] = PM25_TIERS,
        rolling_hours: int = 24,
        min_valid_readings_24h: int = 18,
        monitoring_readings: int = 48,
        persistence_ratio: float = 0.75,
        station_catalog_path: str | Path | None = DEFAULT_STATION_CATALOG,
    ) -> None:
        self.pollutant = pollutant
        self.tiers = tuple(sorted(tiers, key=lambda tier: tier.severity))
        self.rolling_window = f"{rolling_hours}h"
        self.min_valid_readings_24h = min_valid_readings_24h
        self.monitoring_readings = monitoring_readings
        self.persistence_ratio = persistence_ratio
        self.station_catalog_path = Path(station_catalog_path) if station_catalog_path else None
        self._station_catalog: pd.DataFrame | None = None

    def run_pipeline(
        self, input_path: str | Path, output_path: str | Path | None = None
    ) -> pd.DataFrame:
        """Ejecuta lectura, normalización, cálculo y exportación opcional a CSV."""
        raw_df = self.read_file(input_path)
        normalized_df = self.normalize(raw_df)
        calculated_df = self.calculate(normalized_df)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            calculated_df.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info("Memoria de cálculo CSV guardada en %s", output_path)

        return calculated_df

    def export_memory_excel(self, calculated_df: pd.DataFrame, output_path: str | Path) -> Path:
        """Genera una memoria de cálculo en Excel con resumen, detalle y parámetros."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary = self.to_station_summary(calculated_df)
        parameters = pd.DataFrame(
            [
                ["Contaminante", self.pollutant],
                ["Ventana de media móvil", self.rolling_window],
                ["Mínimo lecturas válidas 24h", self.min_valid_readings_24h],
                ["Lecturas de seguimiento", self.monitoring_readings],
                ["Criterio de persistencia", f"> {self.persistence_ratio:.0%}"],
                ["Umbral Prevención PM2.5", "38 - 55 µg/m³"],
                ["Umbral Alerta PM2.5", "56 - 150 µg/m³"],
                ["Umbral Emergencia PM2.5", ">= 151 µg/m³"],
                ["Nota normativa", "El umbral >=355 µg/m³ corresponde a PM10, no a PM2.5."],
            ],
            columns=["Parámetro", "Valor"],
        )
        dictionary = pd.DataFrame(
            [
                [
                    "source_format",
                    "Formato detectado: sisaire_hourly_report, sisaire_daily_24h_report, car_long_report o manual_input.",
                ],
                ["rolling_avg_24h", "Media móvil de 24 horas por estación."],
                ["tier_actual", "Clasificación de cada media móvil según rangos PM2.5."],
                ["alert_candidate", "Indica que la media móvil se encuentra en Prevención, Alerta o Emergencia."],
                [
                    "monitoring_type",
                    "declaration para declaratoria; closure para finalización o recategorización.",
                ],
                [
                    "same_range_ratio",
                    "Proporción de las 48 lecturas posteriores que permanecen en el mismo rango del candidato.",
                ],
                [
                    "below_lower_ratio",
                    "Proporción de las 48 lecturas posteriores por debajo del límite inferior del estado declarado.",
                ],
                ["declared_alert", "Marca una declaratoria o mantenimiento confirmado del nivel."],
                ["finalized_alert", "Marca la finalización del estado excepcional."],
                ["recategorized_alert", "Marca una recategorización del estado declarado."],
                ["station_current_status", "Estado vigente por estación para visualización en mapa."],
            ],
            columns=["Campo", "Descripción"],
        )

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="Resumen_Estaciones", index=False)
            calculated_df.to_excel(writer, sheet_name="Memoria_Calculo", index=False)
            parameters.to_excel(writer, sheet_name="Parametros", index=False)
            dictionary.to_excel(writer, sheet_name="Diccionario", index=False)

            workbook = writer.book
            for sheet_name in workbook.sheetnames:
                worksheet = workbook[sheet_name]
                worksheet.freeze_panes = "A2"
                for cell in worksheet[1]:
                    cell.style = "Headline 3"
                for column_cells in worksheet.columns:
                    max_length = max(
                        len(str(cell.value)) if cell.value is not None else 0
                        for cell in column_cells
                    )
                    adjusted_width = min(max(max_length + 2, 12), 42)
                    worksheet.column_dimensions[column_cells[0].column_letter].width = adjusted_width

        logger.info("Memoria de cálculo Excel guardada en %s", output_path)
        return output_path

    def read_file(self, input_path: str | Path) -> pd.DataFrame:
        """Lee CSV o Excel probando separadores y codificaciones comunes."""
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo de entrada: {path}")

        suffix = path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(path)

        if suffix == ".csv":
            last_error: Exception | None = None
            for encoding in ("utf-8-sig", "utf-8", "latin1", "cp1252"):
                for sep in (None, ";", ","):
                    try:
                        return pd.read_csv(path, sep=sep, engine="python", encoding=encoding)
                    except Exception as exc:  # pragma: no cover - fallback operativo
                        last_error = exc
            raise ValueError(f"No fue posible leer el CSV {path}: {last_error}")

        raise ValueError("Formato no soportado. Use CSV, XLSX o XLS.")

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza nombres de columnas, tipos, granularidad y coordenadas."""
        if df.empty:
            raise ValueError("El archivo de entrada no contiene registros.")

        clean_df = df.copy()
        clean_df.columns = [str(column).strip().replace("\ufeff", "") for column in clean_df.columns]
        mapped_columns = self._resolve_columns(clean_df.columns)

        raw_start = self._required_column(clean_df, mapped_columns.get("start_time"), "fecha inicial")
        raw_end = self._optional_column(clean_df, mapped_columns.get("end_time"))

        records = pd.DataFrame(index=clean_df.index)
        records["station_id"] = self._optional_column(clean_df, mapped_columns.get("station_id"))
        records["station_name"] = self._required_column(
            clean_df, mapped_columns.get("station_name"), "estación"
        )
        records["pollutant"] = self._extract_pollutant(clean_df, mapped_columns)
        records["timestamp"] = self._parse_datetime(raw_start)
        records["end_time"] = self._parse_datetime(raw_end)
        records["value"] = self._parse_number(
            self._required_column(clean_df, mapped_columns.get("value"), "valor/medición")
        )
        records["latitude"] = self._parse_number(
            self._optional_column(clean_df, mapped_columns.get("latitude"))
        )
        records["longitude"] = self._parse_number(
            self._optional_column(clean_df, mapped_columns.get("longitude"))
        )
        records["altitude"] = self._parse_number(
            self._optional_column(clean_df, mapped_columns.get("altitude"))
        )
        records["input_granularity"] = self._detect_input_granularity(raw_start, raw_end)
        records["source_format"] = self._detect_source_format(
            clean_df.columns, records["input_granularity"]
        )
        records["reading_interval_minutes"] = self._detect_reading_interval_minutes(
            raw_start, raw_end
        )

        records = records.dropna(subset=["station_name", "timestamp", "value"])
        records["station_name"] = records["station_name"].astype(str).str.strip()
        records["pollutant"] = records["pollutant"].fillna(self.pollutant).astype(str).str.strip()

        accepted_pollutants = self._accepted_pollutants(self.pollutant)
        if mapped_columns.get("pollutant") and accepted_pollutants:
            mask = records["pollutant"].str.upper().isin({item.upper() for item in accepted_pollutants})
            filtered = records.loc[mask].copy()
            if filtered.empty:
                raise ValueError(f"No se encontraron datos para el contaminante {self.pollutant}.")
            records = filtered

        records = self._enrich_with_station_catalog(records)
        records["station_id"] = records["station_id"].where(
            records["station_id"].notna(), records["station_name"]
        )
        records["station_id"] = records["station_id"].astype(str).str.strip()
        records["pollutant"] = self.pollutant
        records = records.sort_values(["station_name", "timestamp"]).reset_index(drop=True)

        if records.empty:
            raise ValueError("Después de normalizar no quedaron registros válidos para calcular.")

        return records

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula media móvil de 24h y aplica declaratoria/cierre por estación."""
        calculated = df.copy().sort_values(["station_name", "timestamp"]).reset_index(drop=True)
        calculated["input_granularity"] = calculated.get("input_granularity", "hourly")

        calculated["valid_readings_24h"] = 0.0
        calculated["rolling_avg_24h"] = pd.NA

        hourly_mask = calculated["input_granularity"] != "daily_24h_average"
        daily_mask = calculated["input_granularity"] == "daily_24h_average"

        if hourly_mask.any():
            hourly = calculated.loc[hourly_mask].copy()
            calculated.loc[hourly_mask, "valid_readings_24h"] = (
                hourly.groupby("station_name")
                .rolling(self.rolling_window, on="timestamp")["value"]
                .count()
                .reset_index(level=0, drop=True)
                .to_numpy()
            )
            calculated.loc[hourly_mask, "rolling_avg_24h"] = (
                hourly.groupby("station_name")
                .rolling(self.rolling_window, on="timestamp")["value"]
                .mean()
                .reset_index(level=0, drop=True)
                .round(3)
                .to_numpy()
            )

        if daily_mask.any():
            # El reporte SISAIRE diario tipo `Estacion, Fecha inicial, PM2.5` trae valores
            # preagregados de 24h. Se conserva el valor como media trazable.
            calculated.loc[daily_mask, "valid_readings_24h"] = 24
            calculated.loc[daily_mask, "rolling_avg_24h"] = calculated.loc[daily_mask, "value"].round(3)

        calculated["is_complete_24h"] = calculated["valid_readings_24h"] >= self.min_valid_readings_24h
        calculated.loc[~calculated["is_complete_24h"], "rolling_avg_24h"] = pd.NA

        tier_data = calculated["rolling_avg_24h"].apply(self._classify_tier)
        calculated["tier_actual"] = tier_data.apply(lambda item: item["tier"])
        calculated["tier_severity"] = tier_data.apply(lambda item: item["severity"])
        calculated["threshold_lower"] = tier_data.apply(lambda item: item["lower"])
        calculated["alert_candidate"] = calculated["tier_severity"] > 0

        calculated = self._apply_monitoring(calculated)
        return calculated[
            [column for column in MEMORY_COLUMNS if column in calculated.columns]
            + [column for column in calculated.columns if column not in MEMORY_COLUMNS]
        ]

    def to_station_summary(self, calculated_df: pd.DataFrame) -> pd.DataFrame:
        """Devuelve el último estado y medición disponible por estación."""
        if calculated_df.empty:
            return calculated_df

        ordered = calculated_df.sort_values(["station_name", "timestamp"])
        latest = ordered.groupby("station_name", as_index=False).tail(1).copy()
        columns = [
            "station_id",
            "station_name",
            "pollutant",
            "timestamp",
            "value",
            "rolling_avg_24h",
            "station_current_status",
            "state_tier",
            "tier_actual",
            "latitude",
            "longitude",
            "altitude",
        ]
        return latest[[column for column in columns if column in latest.columns]].reset_index(drop=True)

    def to_geojson(self, calculated_df: pd.DataFrame) -> dict:
        """Construye GeoJSON con el estado actual por estación."""
        summary = self.to_station_summary(calculated_df)
        return self.summary_to_geojson(summary)

    def summary_to_geojson(self, summary: pd.DataFrame) -> dict:
        features = []
        if summary.empty:
            return {"type": "FeatureCollection", "features": features}

        for _, row in summary.dropna(subset=["latitude", "longitude"]).iterrows():
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(row["longitude"]), float(row["latitude"])],
                    },
                    "properties": {
                        "station_id": str(row.get("station_id", "")),
                        "station_name": row.get("station_name", ""),
                        "pollutant": row.get("pollutant", self.pollutant),
                        "timestamp": row["timestamp"].isoformat()
                        if pd.notna(row.get("timestamp"))
                        else None,
                        "value": None if pd.isna(row.get("value")) else float(row.get("value")),
                        "rolling_avg_24h": None
                        if pd.isna(row.get("rolling_avg_24h"))
                        else float(row.get("rolling_avg_24h")),
                        "estado_actual": row.get("station_current_status", "Sin dato"),
                        "state_tier": row.get("state_tier", "Normal"),
                        "tier_actual": row.get("tier_actual", "Sin dato"),
                        "altitude": None
                        if pd.isna(row.get("altitude"))
                        else float(row.get("altitude")),
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}

    def station_catalog_geojson(self) -> dict:
        """Devuelve el catálogo local completo de estaciones como GeoJSON."""
        catalog = self._load_station_catalog()
        if catalog.empty:
            return {"type": "FeatureCollection", "features": []}
        summary = catalog.rename(
            columns={
                "catalog_station_id": "station_id",
                "catalog_station_name": "station_name",
                "catalog_latitude": "latitude",
                "catalog_longitude": "longitude",
                "catalog_altitude": "altitude",
            }
        )
        summary["pollutant"] = self.pollutant
        summary["timestamp"] = pd.NaT
        summary["value"] = pd.NA
        summary["rolling_avg_24h"] = pd.NA
        summary["station_current_status"] = "Sin dato"
        summary["tier_actual"] = "Sin dato"
        summary["state_tier"] = "Sin dato"
        return self.summary_to_geojson(summary)

    def _apply_monitoring(self, calculated: pd.DataFrame) -> pd.DataFrame:
        calculated = calculated.copy()
        calculated["monitoring_status"] = "Sin observación"
        calculated["monitoring_type"] = ""
        calculated["monitoring_track_id"] = ""
        calculated["monitoring_target_tier"] = ""
        calculated["monitoring_start"] = pd.NaT
        calculated["monitoring_end"] = pd.NaT
        calculated["monitoring_threshold"] = pd.NA
        calculated["monitoring_readings_count"] = 0
        calculated["same_range_readings_count"] = 0
        calculated["same_range_ratio"] = pd.NA
        calculated["exceedance_readings_count"] = 0
        calculated["exceedance_ratio"] = pd.NA
        calculated["below_lower_readings_count"] = 0
        calculated["below_lower_ratio"] = pd.NA
        calculated["parallel_monitoring_count"] = 0
        calculated["active_monitoring_ids"] = ""
        calculated["monitoring_event"] = ""
        calculated["declared_alert"] = False
        calculated["declared_tier"] = ""
        calculated["finalized_alert"] = False
        calculated["recategorized_alert"] = False
        calculated["state_transition"] = ""
        calculated["calculation_status"] = "Normal"
        calculated["station_current_status"] = "Normal"
        calculated["state_tier"] = "Normal"
        calculated["state_started_at"] = pd.NaT

        for _, station_indexes in calculated.groupby("station_name").groups.items():
            indexes = list(station_indexes)
            valid_positions = [
                position
                for position, index in enumerate(indexes)
                if bool(calculated.at[index, "is_complete_24h"])
            ]
            if not valid_positions:
                continue

            active_tracks: list[MonitoringTrack] = []
            track_counter = 0
            current_state: dict[str, Any] | None = None

            for position, index in enumerate(indexes):
                # 1. Cerrar seguimientos cuya ventana de 48 lecturas termina en esta posición.
                completed_tracks = [
                    track for track in active_tracks if track.end_position == position
                ]
                for track in completed_tracks:
                    self._evaluate_track(calculated, indexes, track, current_state)
                    if track.kind == "declaration":
                        current_state = self._apply_declaration_result(
                            calculated, indexes, track, current_state
                        )
                    elif track.kind == "closure":
                        current_state = self._apply_closure_result(
                            calculated, indexes, track, current_state
                        )

                active_tracks = [track for track in active_tracks if track.end_position != position]

                # 2. Iniciar seguimiento de declaratoria cada vez que una media móvil entra en un rango.
                if bool(calculated.at[index, "alert_candidate"]):
                    track_counter += 1
                    track = self._build_declaration_track(
                        calculated, indexes, valid_positions, position, index, track_counter
                    )
                    self._register_track(calculated, indexes, track)
                    if track.end_position is not None:
                        active_tracks.append(track)

                # 3. Si ya existe estado declarado y el valor baja del límite inferior,
                # iniciar seguimiento de finalización/recategorización.
                if current_state and bool(calculated.at[index, "is_complete_24h"]):
                    current_avg = calculated.at[index, "rolling_avg_24h"]
                    if pd.notna(current_avg) and float(current_avg) < float(current_state["lower"]):
                        track_counter += 1
                        track = self._build_closure_track(
                            calculated,
                            indexes,
                            valid_positions,
                            position,
                            index,
                            track_counter,
                            current_state,
                        )
                        self._register_track(calculated, indexes, track)
                        if track.end_position is not None:
                            active_tracks.append(track)

                # 4. Estado vigente para esta lectura.
                self._write_current_state(calculated, index, current_state)

        return calculated

    def _build_declaration_track(
        self,
        calculated: pd.DataFrame,
        indexes: list[int],
        valid_positions: list[int],
        position: int,
        index: int,
        track_counter: int,
    ) -> MonitoringTrack:
        window_positions = self._next_valid_positions(valid_positions, position, self.monitoring_readings)
        station_slug = self._track_station_slug(calculated.at[index, "station_name"])
        return MonitoringTrack(
            track_id=f"{station_slug}-DEC-{track_counter:04d}",
            kind="declaration",
            start_position=position,
            start_index=index,
            start_time=calculated.at[index, "timestamp"],
            evaluation_positions=window_positions,
            target_tier=str(calculated.at[index, "tier_actual"]),
            target_severity=int(calculated.at[index, "tier_severity"]),
            threshold_lower=float(calculated.at[index, "threshold_lower"]),
        )

    def _build_closure_track(
        self,
        calculated: pd.DataFrame,
        indexes: list[int],
        valid_positions: list[int],
        position: int,
        index: int,
        track_counter: int,
        current_state: dict[str, Any],
    ) -> MonitoringTrack:
        window_positions = self._next_valid_positions(valid_positions, position, self.monitoring_readings)
        station_slug = self._track_station_slug(calculated.at[index, "station_name"])
        return MonitoringTrack(
            track_id=f"{station_slug}-FIN-{track_counter:04d}",
            kind="closure",
            start_position=position,
            start_index=index,
            start_time=calculated.at[index, "timestamp"],
            evaluation_positions=window_positions,
            target_tier=str(current_state["tier"]),
            target_severity=int(current_state["severity"]),
            threshold_lower=float(current_state["lower"]),
        )

    def _register_track(
        self,
        calculated: pd.DataFrame,
        indexes: list[int],
        track: MonitoringTrack,
    ) -> None:
        start_index = track.start_index
        start_label = "Declaratoria" if track.kind == "declaration" else "Cierre/recategorización"
        self._append_event(calculated, start_index, f"{start_label} iniciada: {track.track_id}")

        calculated.at[start_index, "monitoring_status"] = (
            "Observación iniciada"
            if track.evaluation_positions
            else "Observación iniciada sin datos suficientes"
        )
        calculated.at[start_index, "monitoring_type"] = track.kind
        calculated.at[start_index, "monitoring_track_id"] = track.track_id
        calculated.at[start_index, "monitoring_target_tier"] = track.target_tier
        calculated.at[start_index, "monitoring_start"] = track.start_time
        calculated.at[start_index, "monitoring_threshold"] = track.threshold_lower

        if len(track.evaluation_positions) < self.monitoring_readings:
            calculated.at[start_index, "calculation_status"] = "Observación incompleta"
            return

        end_index = indexes[track.evaluation_positions[-1]]
        window_time = calculated.at[end_index, "timestamp"]
        for window_position in track.evaluation_positions:
            window_index = indexes[window_position]
            current_ids = [
                value
                for value in str(calculated.at[window_index, "active_monitoring_ids"]).split("|")
                if value
            ]
            current_ids.append(track.track_id)
            calculated.at[window_index, "active_monitoring_ids"] = "|".join(current_ids)
            calculated.at[window_index, "parallel_monitoring_count"] = len(current_ids)
            if calculated.at[window_index, "calculation_status"] == "Normal":
                calculated.at[window_index, "calculation_status"] = "Observación activa"
            if calculated.at[window_index, "monitoring_status"] == "Sin observación":
                calculated.at[window_index, "monitoring_status"] = "En observación"

        calculated.at[start_index, "monitoring_end"] = window_time

    def _evaluate_track(
        self,
        calculated: pd.DataFrame,
        indexes: list[int],
        track: MonitoringTrack,
        current_state: dict[str, Any] | None,
    ) -> None:
        if len(track.evaluation_positions) < self.monitoring_readings or track.end_position is None:
            return

        window_indexes = [indexes[position] for position in track.evaluation_positions]
        end_index = indexes[track.end_position]
        calculated.at[end_index, "monitoring_status"] = "Seguimiento evaluado"
        calculated.at[end_index, "monitoring_type"] = track.kind
        calculated.at[end_index, "monitoring_track_id"] = track.track_id
        calculated.at[end_index, "monitoring_target_tier"] = track.target_tier
        calculated.at[end_index, "monitoring_start"] = track.start_time
        calculated.at[end_index, "monitoring_end"] = calculated.at[end_index, "timestamp"]
        calculated.at[end_index, "monitoring_threshold"] = track.threshold_lower
        calculated.at[end_index, "monitoring_readings_count"] = len(window_indexes)

        if track.kind == "declaration":
            same_count = int((calculated.loc[window_indexes, "tier_actual"] == track.target_tier).sum())
            same_ratio = same_count / len(window_indexes)
            calculated.at[end_index, "same_range_readings_count"] = same_count
            calculated.at[end_index, "same_range_ratio"] = round(same_ratio, 4)
            calculated.at[end_index, "exceedance_readings_count"] = same_count
            calculated.at[end_index, "exceedance_ratio"] = round(same_ratio, 4)
            if same_ratio > self.persistence_ratio:
                calculated.at[end_index, "monitoring_status"] = "Declaratoria validada"
                self._append_event(
                    calculated,
                    end_index,
                    f"{track.track_id}: persistencia {same_ratio:.2%} en {track.target_tier}",
                )
            else:
                calculated.at[end_index, "monitoring_status"] = "Declaratoria descartada"
                calculated.at[end_index, "calculation_status"] = "Declaratoria descartada"
                self._append_event(
                    calculated,
                    end_index,
                    f"{track.track_id}: descartada por persistencia {same_ratio:.2%}",
                )
            return

        below_count = int(
            (calculated.loc[window_indexes, "rolling_avg_24h"] < track.threshold_lower).sum()
        )
        below_ratio = below_count / len(window_indexes)
        calculated.at[end_index, "below_lower_readings_count"] = below_count
        calculated.at[end_index, "below_lower_ratio"] = round(below_ratio, 4)
        if below_ratio > self.persistence_ratio:
            calculated.at[end_index, "monitoring_status"] = "Cierre/recategorización validado"
            self._append_event(
                calculated,
                end_index,
                f"{track.track_id}: {below_ratio:.2%} por debajo de {track.threshold_lower}",
            )
        else:
            calculated.at[end_index, "monitoring_status"] = "Cierre/recategorización descartado"
            self._append_event(
                calculated,
                end_index,
                f"{track.track_id}: descartado, solo {below_ratio:.2%} por debajo",
            )
            if current_state:
                calculated.at[end_index, "calculation_status"] = f"Se mantiene - {current_state['tier']}"

    def _apply_declaration_result(
        self,
        calculated: pd.DataFrame,
        indexes: list[int],
        track: MonitoringTrack,
        current_state: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if track.end_position is None:
            return current_state
        end_index = indexes[track.end_position]
        ratio = calculated.at[end_index, "same_range_ratio"]
        if pd.isna(ratio) or float(ratio) <= self.persistence_ratio:
            return current_state

        # Si ya hay un nivel más crítico vigente, la disminución se procesa por Artículo 13.
        if current_state and track.target_severity < int(current_state["severity"]):
            calculated.at[end_index, "calculation_status"] = f"Se mantiene - {current_state['tier']}"
            self._append_event(
                calculated,
                end_index,
                f"{track.track_id}: nivel inferior confirmado, pendiente criterio de recategorización",
            )
            return current_state

        if current_state is None:
            transition = f"Declarada - {track.target_tier}"
            state_started_at = calculated.at[end_index, "timestamp"]
        elif track.target_severity > int(current_state["severity"]):
            transition = f"Recategorizada ascendente - {track.target_tier}"
            state_started_at = calculated.at[end_index, "timestamp"]
        else:
            transition = f"Se mantiene - {track.target_tier}"
            state_started_at = current_state["started_at"]

        calculated.at[end_index, "declared_alert"] = True
        calculated.at[end_index, "declared_tier"] = track.target_tier
        calculated.at[end_index, "state_transition"] = transition
        calculated.at[end_index, "calculation_status"] = transition

        return {
            "tier": track.target_tier,
            "severity": track.target_severity,
            "lower": track.threshold_lower,
            "started_at": state_started_at,
        }

    def _apply_closure_result(
        self,
        calculated: pd.DataFrame,
        indexes: list[int],
        track: MonitoringTrack,
        current_state: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if track.end_position is None or current_state is None:
            return current_state
        end_index = indexes[track.end_position]
        ratio = calculated.at[end_index, "below_lower_ratio"]
        if pd.isna(ratio) or float(ratio) <= self.persistence_ratio:
            return current_state

        window_indexes = [indexes[position] for position in track.evaluation_positions]
        resulting_tier = self._dominant_tier_below_threshold(
            calculated.loc[window_indexes], threshold=track.threshold_lower
        )
        resulting_severity = self._tier_severity_by_name(resulting_tier)

        if resulting_severity > 0:
            if resulting_severity == int(current_state["severity"]):
                transition = f"Se mantiene - {resulting_tier}"
                state_started_at = current_state["started_at"]
            else:
                transition = f"Recategorizada - {resulting_tier}"
                calculated.at[end_index, "recategorized_alert"] = True
                state_started_at = calculated.at[end_index, "timestamp"]
            calculated.at[end_index, "declared_tier"] = resulting_tier
            new_state = {
                "tier": resulting_tier,
                "severity": resulting_severity,
                "lower": float(self._tier_by_name(resulting_tier).lower),
                "started_at": state_started_at,
            }
        else:
            transition = "Finalizada - Normal"
            calculated.at[end_index, "finalized_alert"] = True
            new_state = None

        calculated.at[end_index, "state_transition"] = transition
        calculated.at[end_index, "calculation_status"] = transition
        return new_state

    def _write_current_state(
        self, calculated: pd.DataFrame, index: int, current_state: dict[str, Any] | None
    ) -> None:
        if current_state:
            calculated.at[index, "state_tier"] = current_state["tier"]
            calculated.at[index, "state_started_at"] = current_state["started_at"]
            if not str(calculated.at[index, "calculation_status"]).startswith(
                ("Declarada", "Recategorizada", "Finalizada", "Se mantiene")
            ):
                calculated.at[index, "calculation_status"] = f"Estado vigente - {current_state['tier']}"
            calculated.at[index, "station_current_status"] = f"Declarada - {current_state['tier']}"
        else:
            calculated.at[index, "state_tier"] = "Normal"
            calculated.at[index, "station_current_status"] = "Normal"
            if str(calculated.at[index, "calculation_status"]) == "Normal":
                calculated.at[index, "calculation_status"] = "Normal"

    def _next_valid_positions(
        self, valid_positions: list[int], position: int, count: int
    ) -> list[int]:
        return [valid_position for valid_position in valid_positions if valid_position > position][
            :count
        ]

    def _dominant_tier_below_threshold(self, window: pd.DataFrame, threshold: float) -> str:
        below = window.loc[window["rolling_avg_24h"] < threshold].copy()
        if below.empty:
            return "Normal"

        counts = Counter(str(value) for value in below["tier_actual"].fillna("Normal"))
        if not counts:
            return "Normal"

        # En caso de empate se escoge el nivel más crítico como criterio conservador.
        return max(counts, key=lambda tier_name: (counts[tier_name], self._tier_severity_by_name(tier_name)))

    def _append_event(self, calculated: pd.DataFrame, index: int, event: str) -> None:
        current = str(calculated.at[index, "monitoring_event"] or "")
        calculated.at[index, "monitoring_event"] = f"{current} | {event}".strip(" |")

    def _track_station_slug(self, station_name: str) -> str:
        normalized = self._normalize_label(station_name)
        return "".join(character for character in normalized.upper() if character.isalnum())[:16]

    def _classify_tier(self, value: float | int | None) -> dict[str, Any]:
        if pd.isna(value):
            return {"tier": "Sin dato", "severity": 0, "lower": pd.NA}

        numeric_value = float(value)
        for tier in self.tiers:
            upper_ok = True if tier.upper is None else numeric_value <= tier.upper
            if numeric_value >= tier.lower and upper_ok:
                return {"tier": tier.name, "severity": tier.severity, "lower": tier.lower}

        return {"tier": "Normal", "severity": 0, "lower": pd.NA}

    def _tier_name_by_severity(self, severity: int) -> str:
        for tier in self.tiers:
            if tier.severity == severity:
                return tier.name
        return "Normal"

    def _tier_severity_by_name(self, name: str) -> int:
        if name == "Normal":
            return 0
        for tier in self.tiers:
            if tier.name == name:
                return tier.severity
        return 0

    def _tier_by_name(self, name: str) -> ThresholdTier:
        for tier in self.tiers:
            if tier.name == name:
                return tier
        raise ValueError(f"Tier no configurado: {name}")

    def _resolve_columns(self, columns: Iterable[str]) -> dict[str, str]:
        normalized_lookup = {self._normalize_label(column): column for column in columns}
        resolved: dict[str, str] = {}
        for canonical, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                normalized_alias = self._normalize_label(alias)
                if normalized_alias in normalized_lookup:
                    resolved[canonical] = normalized_lookup[normalized_alias]
                    break

        for alias in self._accepted_pollutants(self.pollutant):
            normalized_alias = self._normalize_label(alias)
            if normalized_alias in normalized_lookup:
                resolved["value"] = normalized_lookup[normalized_alias]
                break

        return resolved

    def _extract_pollutant(self, df: pd.DataFrame, mapped_columns: dict[str, str]) -> pd.Series:
        pollutant_column = mapped_columns.get("pollutant")
        if pollutant_column:
            return df[pollutant_column]
        return pd.Series([self.pollutant] * len(df), index=df.index)

    def _required_column(self, df: pd.DataFrame, column: str | None, label: str) -> pd.Series:
        if not column or column not in df.columns:
            raise ValueError(f"No se encontró la columna requerida de {label}.")
        return df[column]

    def _optional_column(self, df: pd.DataFrame, column: str | None) -> pd.Series:
        if column and column in df.columns:
            return df[column]
        return pd.Series([pd.NA] * len(df), index=df.index)

    def _parse_number(self, series: pd.Series) -> pd.Series:
        text = series.astype(str).str.strip()
        text = text.str.replace("\u00a0", "", regex=False)
        # Si viene como 1.234,56 se remueve el separador de miles. Si viene como
        # 4.923668 o -74.053345 se mantiene el punto decimal.
        has_decimal_comma = text.str.contains(",", na=False)
        text = text.where(~has_decimal_comma, text.str.replace(".", "", regex=False))
        text = text.str.replace(",", ".", regex=False)
        text = text.str.replace(r"[^0-9.\-]", "", regex=True)
        return pd.to_numeric(text, errors="coerce")

    def _parse_datetime(self, series: pd.Series) -> pd.Series:
        if pd.api.types.is_datetime64_any_dtype(series):
            return pd.to_datetime(series, errors="coerce")

        text = series.astype(str).str.strip()
        empty_mask = text.isin(["", "<NA>", "nan", "NaN", "NaT", "None"])
        parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

        slash_date_mask = text.str.match(r"^\d{1,2}/\d{1,2}/\d{4}", na=False) & ~empty_mask
        if slash_date_mask.any():
            slash_values = text.loc[slash_date_mask]
            parsed_slash = pd.to_datetime(
                slash_values, errors="coerce", format="%d/%m/%Y %I:%M:%S %p"
            )
            missing_slash = parsed_slash.isna()
            if missing_slash.any():
                parsed_slash.loc[missing_slash] = pd.to_datetime(
                    slash_values.loc[missing_slash], errors="coerce", dayfirst=True
                )
            parsed.loc[slash_date_mask] = parsed_slash

        remaining_mask = ~slash_date_mask & ~empty_mask
        if remaining_mask.any():
            parsed.loc[remaining_mask] = pd.to_datetime(text.loc[remaining_mask], errors="coerce")

        missing_mask = parsed.isna() & ~empty_mask
        if missing_mask.any():
            parsed.loc[missing_mask] = pd.to_datetime(
                text.loc[missing_mask], errors="coerce", dayfirst=True
            )
        return parsed

    def _detect_source_format(self, columns: Iterable[str], granularity: pd.Series) -> pd.Series:
        """Identifica el formato de origen para trazabilidad de la memoria de cálculo."""
        normalized_columns = {self._normalize_label(column) for column in columns}
        is_sisaire_report = {"estacion", "fecha inicial", "pm2.5"}.issubset(
            normalized_columns
        )
        is_car_long_report = {"med concentracion estandar", "fecha inicio"}.issubset(
            normalized_columns
        )

        if is_sisaire_report:
            values = [
                "sisaire_daily_24h_report" if item == "daily_24h_average" else "sisaire_hourly_report"
                for item in granularity
            ]
        elif is_car_long_report:
            values = ["car_long_report"] * len(granularity)
        else:
            values = ["manual_input"] * len(granularity)
        return pd.Series(values, index=granularity.index)

    def _detect_reading_interval_minutes(
        self, start_series: pd.Series, end_series: pd.Series
    ) -> pd.Series:
        """Estima la resolución de la lectura a partir de Fecha inicial/final."""
        start = self._parse_datetime(start_series)
        end = self._parse_datetime(end_series)
        interval = (end - start).dt.total_seconds().div(60).round()
        interval = interval.where(interval.isna(), interval + 1)

        missing_or_invalid = interval.isna() | (interval <= 0)
        if missing_or_invalid.any():
            sorted_start = start.sort_values()
            inferred = sorted_start.diff().dt.total_seconds().div(60).median()
            if pd.notna(inferred) and inferred > 0:
                interval.loc[missing_or_invalid] = inferred

        return interval

    def _detect_input_granularity(self, start_series: pd.Series, end_series: pd.Series) -> pd.Series:
        start_text = start_series.astype(str).str.strip()
        end_text = end_series.astype(str).str.strip()
        has_time_component = start_text.str.contains(r"\d{1,2}:\d{2}", regex=True, na=False)
        end_has_value = ~end_text.isin(["", "<NA>", "nan", "NaN", "NaT", "None"])
        daily_like = ~has_time_component & ~end_has_value
        return pd.Series(
            ["daily_24h_average" if is_daily else "hourly" for is_daily in daily_like],
            index=start_series.index,
        )

    def _accepted_pollutants(self, pollutant: str) -> set[str]:
        return POLLUTANT_ALIASES.get(pollutant.upper(), {pollutant})

    def _load_station_catalog(self) -> pd.DataFrame:
        if self._station_catalog is not None:
            return self._station_catalog

        if not self.station_catalog_path or not self.station_catalog_path.exists():
            self._station_catalog = pd.DataFrame()
            return self._station_catalog

        catalog = pd.read_csv(self.station_catalog_path, encoding="utf-8-sig")
        catalog.columns = [str(column).strip() for column in catalog.columns]
        rename_map = {
            "station_id": "catalog_station_id",
            "station_name": "catalog_station_name",
            "latitude": "catalog_latitude",
            "longitude": "catalog_longitude",
            "altitude": "catalog_altitude",
        }
        catalog = catalog.rename(columns=rename_map)
        catalog["station_name_key"] = catalog["catalog_station_name"].apply(self._normalize_label)
        for column in ("catalog_latitude", "catalog_longitude", "catalog_altitude"):
            if column in catalog:
                catalog[column] = self._parse_number(catalog[column])
        self._station_catalog = catalog
        return catalog

    def _enrich_with_station_catalog(self, records: pd.DataFrame) -> pd.DataFrame:
        catalog = self._load_station_catalog()
        if catalog.empty or "catalog_station_name" not in catalog.columns:
            return records

        enriched = records.copy()
        enriched["station_name_key"] = enriched["station_name"].apply(self._normalize_label)
        merge_columns = [
            "station_name_key",
            "catalog_station_id",
            "catalog_station_name",
            "catalog_latitude",
            "catalog_longitude",
            "catalog_altitude",
        ]
        catalog = catalog[[column for column in merge_columns if column in catalog.columns]]
        catalog = catalog.drop_duplicates("station_name_key")
        enriched = enriched.merge(catalog, on="station_name_key", how="left")

        missing_station_id = enriched["station_id"].isna() | (
            enriched["station_id"].astype(str).str.strip() == ""
        )
        enriched.loc[missing_station_id, "station_id"] = enriched.loc[
            missing_station_id, "catalog_station_id"
        ]

        for target, source in (
            ("latitude", "catalog_latitude"),
            ("longitude", "catalog_longitude"),
            ("altitude", "catalog_altitude"),
        ):
            if target in enriched and source in enriched:
                enriched[target] = enriched[target].fillna(enriched[source])

        return enriched.drop(
            columns=[
                column
                for column in [
                    "station_name_key",
                    "catalog_station_id",
                    "catalog_station_name",
                    "catalog_latitude",
                    "catalog_longitude",
                    "catalog_altitude",
                ]
                if column in enriched.columns
            ]
        )

    def _normalize_label(self, label: str) -> str:
        return (
            str(label)
            .strip()
            .lower()
            .replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ñ", "n")
            .replace("_", " ")
            .replace("-", " ")
        )


# Compatibilidad con el nombre anterior usado por el proyecto.
ProcessorPM25 = AirQualityAlertEngine


if __name__ == "__main__":
    engine = AirQualityAlertEngine()
    result = engine.run_pipeline("./data/reporte-TEST.csv", "./data/reporte-fin.csv")
    print(result.head())
