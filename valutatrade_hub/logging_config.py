"""Настройка логирования: формат, уровень, ротация файлов."""

import logging
import os
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

LOGGER_NAME = "valutatrade"
PARSER_LOGGER_NAME = "valutatrade.parser"


def _file_handler(path: str, settings: SettingsLoader) -> RotatingFileHandler:
    """Файловый обработчик с ротацией по размеру."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=settings.get("log_max_bytes"),
        backupCount=settings.get("log_backup_count"),
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(settings.get("log_format"), datefmt="%Y-%m-%dT%H:%M:%S")
    )
    return handler


def setup_logging() -> logging.Logger:
    """Настраивает логи.

    - операции (BUY/SELL/...) — logs/actions.log;
    - Parser Service — logs/parser.log и консоль («INFO: ...»).
    Формат строковый (человекочитаемый), уровень по умолчанию INFO.
    """
    settings = SettingsLoader()
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:  # уже настроен
        return logger

    logger.addHandler(_file_handler(settings.get("log_file"), settings))
    logger.setLevel(settings.get("log_level"))

    parser_logger = logging.getLogger(PARSER_LOGGER_NAME)
    parser_logger.propagate = False  # не дублировать в actions.log
    parser_logger.addHandler(_file_handler(settings.get("parser_log_file"), settings))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    parser_logger.addHandler(console)
    parser_logger.setLevel(settings.get("log_level"))
    return logger
