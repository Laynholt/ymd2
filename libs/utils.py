import os
import re
import logging

import config
from libs import myfromatter


def setup_logger(logger: logging.Logger, logger_type: int) -> None:
    logger.setLevel(logger_type)

    os.makedirs(config.paths['dirs']['stuff'], exist_ok=True)
    if os.path.exists(config.paths['files']['log']):
        os.remove(config.paths['files']['log'])

    file_handler = logging.FileHandler(config.paths['files']['log'], encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(myfromatter.logger_format))
    logger.addHandler(file_handler)

    if not config.LOGGER_WITHOUT_CONSOLE:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(myfromatter.CustomFormatter())
        logger.addHandler(console_handler)


def strip_bad_symbols(text: str, soft_mode: bool = False) -> str:
    if soft_mode:
        result = re.sub(r"[^\w!@#$%^&)(_+}\]\[{,.;= -]", "", text)
    else:
        result = re.sub(r"[^\w_.)( -]", "", text)
    return result
