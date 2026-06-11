"""Motor de cálculo para alertas de calidad del aire.

El motor acepta archivos CSV o Excel y normaliza formatos reales de SISAIRE:

- Formato largo CAR/SISAIRE con `;`, `MED_CONCENTRACION_ESTANDAR`, `FECHA_INICIO`,
  `LATITUD`, `LONGITUD` y `MSFL_CODE`.
- Reporte descargado desde SISAIRE con columnas como `Estacion`, `Fecha inicial`,
  `Fecha final` y `PM2.5`, normalmente sin coordenadas.
- Archivos manuales con nombres equivalentes en español o inglés.

Después de normalizar, enriquece estaciones sin coordenadas usando el catálogo local
`data/catalog/stations_sisaire_car.csv`, calcula medias móviles de 24 horas por
estación y aplica una regla de persistencia de 48 lecturas con más del 75 % del tiempo
sobre el umbral.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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
    "threshold_lower",
    "alert_candidate",
    "monitoring_status",
    "monitoring_start",
    "monitoring_end",
    "monitoring_threshold",
    "monitoring_readings_count",
    "exceedance_readings_count",
    "exceedance_ratio",
    "declared_alert",
    "declared_tier",
    "calculation_status",
    "station_current_status",
    "latitude",
    "longitude",
    "altitude",
]


class AirQualityAlertEngine:
    """Calcula medias móviles, seguimiento y declaración de alertas."""

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

    def run_pipeline(self, input_path: str | Path, output_path: str | Path | None = None) -> pd.DataFrame:
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
        """Genera una memoria de cálculo en Excel con resumen, detalle y parámetros.

        Esta salida está pensada para revisión funcional: incluye resumen por estación,
        memoria completa, parámetros del modelo y diccionario de columnas.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary = self.to_station_summary(calculated_df)
        parameters = pd.DataFrame(
            [
                ["Contaminante", self.pollutant],
                ["Ventana de media móvil", self.rolling_window],
                ["Mínimo lecturas válidas 24h", self.min_valid_readings_24h],
                ["Lecturas de monitoreo", self.monitoring_readings],
                ["Porcentaje persistencia", self.persistence_ratio],
                ["Umbral Prevención", "38 - 55"],
                ["Umbral Alerta", "56 - 150"],
                ["Umbral Emergencia", ">= 151"],
            ],
            columns=["Parámetro", "Valor"],
        )
        dictionary = pd.DataFrame(
            [
                ["source_format", "Formato detectado del archivo: sisaire_hourly_report, sisaire_daily_24h_report, car_long_report o manual_input."],
                ["reading_interval_minutes", "Resolución estimada de la lectura. Para reporte horario SISAIRE normalmente es 60 minutos."],
                ["value", "Medición original normalizada del contaminante."],
                ["rolling_avg_24h", "Media móvil de 24 horas o promedio 24h preagregado si el reporte viene diario."],
                ["valid_readings_24h", "Cantidad de lecturas válidas en la ventana de 24 horas."],
                ["tier_actual", "Clasificación según umbrales PM2.5."],
                ["alert_candidate", "Indica si la media 24h superó algún umbral."],
                ["monitoring_status", "Estado de la ventana de seguimiento de 48 lecturas."],
                ["exceedance_ratio", "Proporción de lecturas que superaron el umbral durante el seguimiento."],
                ["declared_alert", "Marca la lectura en la que se declara formalmente una alerta."],
                ["station_current_status", "Estado vigente para visualización en mapa."],
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
                    max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
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
        records["station_name"] = self._required_column(clean_df, mapped_columns.get("station_name"), "estación")
        records["pollutant"] = self._extract_pollutant(clean_df, mapped_columns)
        records["timestamp"] = self._parse_datetime(raw_start)
        records["end_time"] = self._parse_datetime(raw_end)
        records["value"] = self._parse_number(
            self._required_column(clean_df, mapped_columns.get("value"), "valor/medición")
        )
        records["latitude"] = self._parse_number(self._optional_column(clean_df, mapped_columns.get("latitude")))
        records["longitude"] = self._parse_number(self._optional_column(clean_df, mapped_columns.get("longitude")))
        records["altitude"] = self._parse_number(self._optional_column(clean_df, mapped_columns.get("altitude")))
        records["input_granularity"] = self._detect_input_granularity(raw_start, raw_end)
        records["source_format"] = self._detect_source_format(clean_df.columns, records["input_granularity"])
        records["reading_interval_minutes"] = self._detect_reading_interval_minutes(raw_start, raw_end)

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
        ).astype(str).str.strip()
        records["pollutant"] = self.pollutant
        records = records.sort_values(["station_name", "timestamp"]).reset_index(drop=True)

        if records.empty:
            raise ValueError("Después de normalizar no quedaron registros válidos para calcular.")

        return records

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula media móvil de 24h, estado por lectura y monitoreo de 48 lecturas."""
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
        calculated = self._append_current_station_status(calculated)
        return calculated[[column for column in MEMORY_COLUMNS if column in calculated.columns] + [column for column in calculated.columns if column not in MEMORY_COLUMNS]]

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
                        "timestamp": row["timestamp"].isoformat() if pd.notna(row.get("timestamp")) else None,
                        "value": None if pd.isna(row.get("value")) else float(row.get("value")),
                        "rolling_avg_24h": None
                        if pd.isna(row.get("rolling_avg_24h"))
                        else float(row.get("rolling_avg_24h")),
                        "estado_actual": row.get("station_current_status", "Sin dato"),
                        "tier_actual": row.get("tier_actual", "Sin dato"),
                        "altitude": None if pd.isna(row.get("altitude")) else float(row.get("altitude")),
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
        return self.summary_to_geojson(summary)

    def _apply_monitoring(self, calculated: pd.DataFrame) -> pd.DataFrame:
        calculated["monitoring_status"] = "Sin monitoreo"
        calculated["monitoring_start"] = pd.NaT
        calculated["monitoring_end"] = pd.NaT
        calculated["monitoring_threshold"] = pd.NA
        calculated["monitoring_readings_count"] = 0
        calculated["exceedance_readings_count"] = 0
        calculated["exceedance_ratio"] = pd.NA
        calculated["declared_alert"] = False
        calculated["declared_tier"] = ""
        calculated["calculation_status"] = "Normal"

        for _, station_indexes in calculated.groupby("station_name").groups.items():
            indexes = list(station_indexes)
            position = 0
            while position < len(indexes):
                current_index = indexes[position]
                current_row = calculated.loc[current_index]

                if not bool(current_row["alert_candidate"]):
                    position += 1
                    continue

                threshold = float(current_row["threshold_lower"])
                candidate_indexes = [
                    index
                    for index in indexes[position:]
                    if bool(calculated.loc[index, "is_complete_24h"])
                ][: self.monitoring_readings]

                if not candidate_indexes:
                    position += 1
                    continue

                start_index = candidate_indexes[0]
                end_index = candidate_indexes[-1]
                monitoring_count = len(candidate_indexes)
                exceedance_count = int((calculated.loc[candidate_indexes, "rolling_avg_24h"] >= threshold).sum())
                exceedance_ratio = exceedance_count / monitoring_count if monitoring_count else 0.0

                calculated.loc[candidate_indexes, "monitoring_status"] = "En seguimiento"
                calculated.loc[candidate_indexes, "monitoring_start"] = calculated.loc[start_index, "timestamp"]
                calculated.loc[candidate_indexes, "monitoring_end"] = calculated.loc[end_index, "timestamp"]
                calculated.loc[candidate_indexes, "monitoring_threshold"] = threshold
                calculated.loc[candidate_indexes, "monitoring_readings_count"] = monitoring_count
                calculated.loc[candidate_indexes, "exceedance_readings_count"] = exceedance_count
                calculated.loc[candidate_indexes, "exceedance_ratio"] = round(exceedance_ratio, 4)
                calculated.loc[candidate_indexes, "calculation_status"] = "Seguimiento"

                if monitoring_count == self.monitoring_readings:
                    max_severity = int(calculated.loc[candidate_indexes, "tier_severity"].max())
                    declared_tier = self._tier_name_by_severity(max_severity)
                    if exceedance_ratio > self.persistence_ratio:
                        calculated.loc[end_index, "declared_alert"] = True
                        calculated.loc[end_index, "declared_tier"] = declared_tier
                        calculated.loc[end_index, "monitoring_status"] = "Alerta declarada"
                        calculated.loc[end_index, "calculation_status"] = f"Declarada - {declared_tier}"
                    else:
                        calculated.loc[end_index, "monitoring_status"] = "No declarada"
                        calculated.loc[end_index, "calculation_status"] = "No declarada"
                    position = indexes.index(end_index) + 1
                else:
                    calculated.loc[candidate_indexes, "monitoring_status"] = "Seguimiento incompleto"
                    calculated.loc[candidate_indexes, "calculation_status"] = "Seguimiento incompleto"
                    break

        return calculated

    def _append_current_station_status(self, calculated: pd.DataFrame) -> pd.DataFrame:
        calculated["station_current_status"] = calculated["calculation_status"]
        last_declared_by_station: dict[str, str] = {}

        for index, row in calculated.sort_values(["station_name", "timestamp"]).iterrows():
            station = row["station_name"]
            if row["declared_alert"]:
                last_declared_by_station[station] = row["declared_tier"]

            current_tier = row["tier_actual"]
            calculation_status = str(row["calculation_status"])
            if station in last_declared_by_station and current_tier != "Normal":
                calculated.at[index, "station_current_status"] = f"Declarada - {current_tier}"
            elif current_tier == "Normal" and not calculation_status.startswith("Seguimiento"):
                calculated.at[index, "station_current_status"] = "Normal"

        return calculated

    def _classify_tier(self, value: float | int | None) -> dict:
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
        is_sisaire_report = {"estacion", "fecha inicial", "pm2.5"}.issubset(normalized_columns)
        is_car_long_report = {"med concentracion estandar", "fecha inicio"}.issubset(normalized_columns)

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

    def _detect_reading_interval_minutes(self, start_series: pd.Series, end_series: pd.Series) -> pd.Series:
        """Estima la resolución de la lectura a partir de Fecha inicial/final.

        En reportes horarios SISAIRE, `Fecha final` suele cerrar en HH:59, por lo que
        se suma un minuto para representar una ventana horaria completa de 60 minutos.
        """
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
        catalog = catalog[[column for column in merge_columns if column in catalog.columns]].drop_duplicates("station_name_key")
        enriched = enriched.merge(catalog, on="station_name_key", how="left")

        missing_station_id = enriched["station_id"].isna() | (enriched["station_id"].astype(str).str.strip() == "")
        enriched.loc[missing_station_id, "station_id"] = enriched.loc[missing_station_id, "catalog_station_id"]

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
