"""Настройка логирования: формат, уровень, ротация файлов."""

import logging
import os
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

LOGGER_NAME = "valutatrade"


def setup_logging() -> logging.Logger:
    """Настраивает логгер: файл logs/actions.log с ротацией по размеру.

    Формат строковый (человекочитаемый), уровень по умолчанию INFO.
    """
    settings = SettingsLoader()
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:  # уже настроен
        return logger

    os.makedirs(settings.get("log_dir"), exist_ok=True)
    handler = RotatingFileHandler(
        settings.get("log_file"),
        maxBytes=settings.get("log_max_bytes"),
        backupCount=settings.get("log_backup_count"),
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(settings.get("log_format"), datefmt="%Y-%m-%dT%H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(settings.get("log_level"))
    return logger
