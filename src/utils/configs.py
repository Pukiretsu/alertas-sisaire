import os
import logging
import colorlog
from pathlib import Path
from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parent.parent.parent
env_path = base_dir / ".env"

load_dotenv(dotenv_path=env_path)


class Config:
    # Logger
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Webscrapper
    JSF_TARGET_URL = os.getenv("JSF_TARGET_URL", None)

    # Configs de la base de datos
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "aire_db")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    # URL de conexión SQLAlchemy
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# --- Configuración del Logger con COLORES ---
def setup_logging():
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
        },
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(Config.LOG_LEVEL)


# Ejecutamos la configuración al importar el módulo
setup_logging()
