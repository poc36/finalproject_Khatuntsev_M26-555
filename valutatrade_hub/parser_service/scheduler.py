"""Планировщик периодического обновления курсов."""

import logging
import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.updater import PARSER_LOGGER, create_updater


def run_scheduler(interval_seconds: int | None = None) -> None:
    """Запускает обновление курсов каждые interval_seconds секунд (Ctrl+C — стоп)."""
    setup_logging()
    interval = interval_seconds or SettingsLoader().get("parser_interval_seconds")
    logger = logging.getLogger(PARSER_LOGGER)
    logger.info(f"Scheduler started, interval {interval} s")
    try:
        while True:
            try:
                create_updater().run_update()
            except ApiRequestError as error:
                logger.error(f"Update failed: {error}")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    run_scheduler()
