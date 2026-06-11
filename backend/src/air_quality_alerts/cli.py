"""CLI del proyecto.

Comandos disponibles:
  air-quality-alerts calculate --input ../data/samples/ejemplo_pm25_bogota.csv
  air-quality-alerts download --fecha-inicio 2026-01-01 --fecha-fin 2026-01-02 --estaciones 29586
  air-quality-alerts api
"""

from __future__ import annotations

import argparse

import uvicorn

from air_quality_alerts.config import Settings
from air_quality_alerts.domain.engine import AirQualityAlertEngine
from air_quality_alerts.ingestion.playwright_downloader import SISAIREDownloader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sistema de alertas de calidad del aire - Bogotá")
    subparsers = parser.add_subparsers(dest="command", required=True)

    calculate_parser = subparsers.add_parser("calculate", help="Calcula memoria desde CSV/Excel")
    calculate_parser.add_argument("--input", required=True, help="Ruta del CSV/XLSX de entrada")
    calculate_parser.add_argument(
        "--output",
        default=str(Settings.OUTPUTS_DIR / "memoria_calculo.csv"),
        help="Ruta CSV de salida",
    )
    calculate_parser.add_argument("--pollutant", default="PM2.5", help="Contaminante a evaluar")
    calculate_parser.add_argument(
        "--excel-output",
        default=None,
        help="Ruta opcional para generar memoria de cálculo en Excel (.xlsx)",
    )
    calculate_parser.add_argument(
        "--min-valid-readings",
        type=int,
        default=18,
        help="Mínimo de lecturas válidas para considerar una ventana de 24h",
    )

    download_parser = subparsers.add_parser("download", help="Descarga CSV desde el portal con Playwright")
    download_parser.add_argument("--estaciones", nargs="+", required=True, help="IDs de estaciones")
    download_parser.add_argument("--contaminante", default="PM2.5")
    download_parser.add_argument("--fecha-inicio", required=True)
    download_parser.add_argument("--fecha-fin", required=True)
    download_parser.add_argument("--ruta", default=str(Settings.DOWNLOADS_DIR))
    download_parser.add_argument("--filename", default="sisaire")
    download_parser.add_argument("--headed", action="store_true", help="Ejecuta el navegador visible")

    api_parser = subparsers.add_parser("api", help="Levanta API FastAPI")
    api_parser.add_argument("--host", default=Settings.API_HOST)
    api_parser.add_argument("--port", type=int, default=Settings.API_PORT)

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "calculate":
        engine = AirQualityAlertEngine(
            pollutant=args.pollutant,
            min_valid_readings_24h=args.min_valid_readings,
        )
        result = engine.run_pipeline(args.input, args.output)
        if args.excel_output:
            engine.export_memory_excel(result, args.excel_output)
        print(
            f"Proceso finalizado. Registros calculados: {len(result)}. "
            f"CSV: {args.output}" + (f" | Excel: {args.excel_output}" if args.excel_output else "")
        )
        return

    if args.command == "download":
        downloader = SISAIREDownloader(
            ids_estaciones=args.estaciones,
            contaminante=args.contaminante,
            fecha_ini=args.fecha_inicio,
            fecha_fin=args.fecha_fin,
            ruta=args.ruta,
            filename=args.filename,
            headless=not args.headed,
        )
        output = downloader.start_download()
        print(f"CSV descargado: {output}")
        return

    if args.command == "api":
        uvicorn.run("air_quality_alerts.api.main:app", host=args.host, port=args.port, reload=True)


if __name__ == "__main__":
    main()
