"""
Copyright 2023 laynholt

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

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
