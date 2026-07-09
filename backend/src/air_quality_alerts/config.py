"""Configuración central del backend.

Lee variables desde `backend/.env` o desde un `.env` en la raíz del repositorio.
Los valores por defecto están pensados para ejecutar el proyecto localmente.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

try:  # pragma: no cover - dependencia cosmética
    import colorlog
except ImportError:  # pragma: no cover
    colorlog = None

PACKAGE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PACKAGE_DIR.parents[1]
REPO_ROOT = BACKEND_DIR.parent

for candidate in (BACKEND_DIR / ".env", REPO_ROOT / ".env"):
    if candidate.exists():
        load_dotenv(candidate)


class Settings:
    """Settings operativos de API, scraper y rutas locales."""

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Portal JSF / SISAIRE
    DEFAULT_JSF_TARGET_URL = "https://sisaire.ideam.gov.co/ideam-sisaire-web/consultas.xhtml"
    JSF_TARGET_URL = os.getenv("JSF_TARGET_URL", DEFAULT_JSF_TARGET_URL)
    CHROMIUM_EXECUTABLE_PATH = os.getenv("CHROMIUM_EXECUTABLE_PATH", "")
    PLAYWRIGHT_DEFAULT_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_DEFAULT_TIMEOUT_MS", "120000"))

    # API
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    ALLOWED_ORIGINS = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
    )

    DEFAULT_STATION_IDS = tuple(
        station.strip()
        for station in os.getenv(
            "DEFAULT_STATION_IDS",
            "29586,31877,8249,31862,8254,8243,31867,31866,31865,31860",
        ).split(",")
        if station.strip()
    )

    # Rutas locales
    DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", str(REPO_ROOT / "downloads")))
    OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", str(REPO_ROOT / "outputs")))

    # Persistencia de sesiones/jobs. SQLite es suficiente para desarrollo; en nube usar PostgreSQL/RDS.
    DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{OUTPUTS_DIR / 'calculation_jobs.db'}"


def setup_logging() -> None:
    """Configura logging legible para consola y CI."""

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(Settings.LOG_LEVEL)
        return

    if colorlog:
        formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(Settings.LOG_LEVEL)


setup_logging()
