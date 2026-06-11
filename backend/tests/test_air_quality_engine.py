from datetime import datetime, timedelta

import pandas as pd

from air_quality_alerts.domain.engine import AirQualityAlertEngine


def _hourly_dataframe(values: list[float], station: str = "ESTACION TEST") -> pd.DataFrame:
    start = datetime(2026, 1, 1)
    return pd.DataFrame(
        {
            "Estacion": [station] * len(values),
            "Fecha inicial": [start + timedelta(hours=i) for i in range(len(values))],
            "PM2.5": values,
            "LATITUD": [4.71] * len(values),
            "LONGITUD": [-74.07] * len(values),
        }
    )


def test_declares_prevention_after_48_readings_over_75_percent():
    engine = AirQualityAlertEngine(min_valid_readings_24h=18)
    result = engine.calculate(engine.normalize(_hourly_dataframe([42] * 72)))

    assert result["declared_alert"].any()
    declared = result[result["declared_alert"]].iloc[0]
    assert declared["declared_tier"] == "Prevención"
    assert declared["exceedance_ratio"] > 0.75


def test_does_not_declare_alert_when_persistence_is_not_enough():
    # La primera ventana supera el umbral, pero luego la mayoría baja a normal.
    values = [42] * 24 + [10] * 48
    engine = AirQualityAlertEngine(min_valid_readings_24h=18)
    result = engine.calculate(engine.normalize(_hourly_dataframe(values)))

    assert not result["declared_alert"].any()


def test_generates_geojson_with_station_status():
    engine = AirQualityAlertEngine(min_valid_readings_24h=18)
    result = engine.calculate(engine.normalize(_hourly_dataframe([10] * 30, station="ESTACION MAPA")))
    geojson = engine.to_geojson(result)

    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    assert geojson["features"][0]["properties"]["estado_actual"] == "Normal"


def test_sisaire_daily_report_is_enriched_with_station_catalog():
    engine = AirQualityAlertEngine(min_valid_readings_24h=18)
    raw = pd.DataFrame(
        {
            "Estacion": ["CAJICA - UMNG"] * 2,
            "Fecha inicial": ["2026-05-29", "2026-05-30"],
            "Fecha final": [pd.NA, pd.NA],
            "PM2.5": [6.95, 6.36],
        }
    )

    normalized = engine.normalize(raw)
    result = engine.calculate(normalized)

    assert result.iloc[0]["input_granularity"] == "daily_24h_average"
    assert result.iloc[0]["station_id"] == "31877"
    assert result.iloc[0]["latitude"] == 4.923668
    assert result.iloc[0]["longitude"] == -74.053345
    assert result.iloc[0]["rolling_avg_24h"] == 6.95


def test_sisaire_hourly_report_uses_real_24h_rolling_average(tmp_path):
    sample = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "data"
        / "samples"
        / "reporte_sisaire_pm25_horario.csv"
    )
    engine = AirQualityAlertEngine(min_valid_readings_24h=18)
    result = engine.run_pipeline(sample, tmp_path / "memoria_horaria.csv")

    assert not result.empty
    assert set(result["input_granularity"].unique()) == {"hourly"}
    assert set(result["source_format"].unique()) == {"sisaire_hourly_report"}
    assert result["reading_interval_minutes"].dropna().mode().iloc[0] == 60

    first_complete = result[result["is_complete_24h"]].iloc[0]
    assert first_complete["valid_readings_24h"] == 18
    assert first_complete["rolling_avg_24h"] == 20.321

    full_window = result[result["valid_readings_24h"] == 24].iloc[0]
    assert full_window["rolling_avg_24h"] == 17.5
