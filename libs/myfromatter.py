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

import logging

logger_format = '[%(levelname)s: [%(thread)d] - %(asctime)s] %(message)s'


class CustomFormatter(logging.Formatter):
    _red = "\x1b[31;20m"
    _grey = "\x1b[38;20m"
    _green = "\x1b[32m"
    _yellow = "\x1b[33;20m"
    _bold_red = "\x1b[31;1m"
    _reset = "\x1b[0m"

    _FORMATS = {
        logging.DEBUG: _green + logger_format + _reset,
        logging.INFO: _grey + logger_format + _reset,
        logging.WARNING: _yellow + logger_format + _reset,
        logging.ERROR: _red + logger_format + _reset,
        logging.CRITICAL: _bold_red + logger_format + _reset
    }

    def format(self, record):
        _logger_format = self._FORMATS.get(record.levelno)
        _formatter = logging.Formatter(_logger_format)
        return _formatter.format(record)
