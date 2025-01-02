import os
import logging
from datetime import datetime


def setup_logging(service_name):
    os.makedirs('logs', exist_ok=True)

    logger = logging.getLogger(service_name)
    logger.setLevel(logging.DEBUG)

    log_filename = os.path.join('logs', f"{service_name}_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
