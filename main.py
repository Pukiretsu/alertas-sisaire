import logging
from src.utils.configs import Config

logger = logging.getLogger(__name__)

def main():
    logger.info("Iniciando Sistema Calidad Aire...")
    logger.info(f"Base de datos {Config.DB_HOST}")

if __name__ == "__main__":
    main()
