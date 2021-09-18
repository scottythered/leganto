#!/usr/bin/env python
import logging
from logging.handlers import TimedRotatingFileHandler

logging.basicConfig(
    handlers=[
        TimedRotatingFileHandler("leganto.log", when="midnight"),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
    format="%(asctime)s -- %(levelname)s -- %(filename)s/%(funcName)s -- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

log = logging.getLogger(__name__)
