import logging
from src.utils.configs import Config

logger = logging.getLogger(__name__)

class Engine:
    def calcular_media_movil(self):
        logger.info("hola")


if __name__ == "__main__":
    motor=Engine()
    motor.calcular_media_movil()

