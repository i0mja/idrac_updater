"""Basic logging configuration."""

import logging
from logging.handlers import RotatingFileHandler
import config

formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')

handler = RotatingFileHandler(config.LOG_PATH, maxBytes=5*1024*1024, backupCount=3)
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)
