"""RatesUpdater — координация обновления курсов из всех источников."""

import logging
from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import PARSER_LOGGER_NAME as PARSER_LOGGER
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage


class RatesUpdater:
    """Опрашивает клиентов, объединяет курсы и сохраняет их."""

    def __init__(self, clients: list[BaseApiClient], storage: RatesStorage):
        self.clients = clients
        self.storage = storage
        self.logger = logging.getLogger(PARSER_LOGGER)

    def run_update(self) -> dict:
        """Обновляет курсы. Возвращает итог: число курсов, время, ошибки."""
        self.logger.info("Starting rates update...")
        pairs, history, errors = {}, [], []
        # Время получения курсов: по нему считается свежесть кеша (TTL).
        # Время самого источника сохраняется в истории (timestamp).
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for client in self.clients:
            try:
                rates = client.fetch_rates()
            except ApiRequestError as error:
                self.logger.error(
                    f"Failed to fetch from {client.SOURCE}: {error.reason}"
                )
                errors.append(f"{client.SOURCE}: {error.reason}")
                continue  # отказоустойчивость: продолжаем с другими источниками
            self.logger.info(
                f"Fetching from {client.SOURCE}... OK ({len(rates)} rates)"
            )

            for pair, rate in rates.items():
                timestamp = client.details[pair]["timestamp"]
                from_code, to_code = pair.split("_")
                pairs[pair] = {
                    "rate": rate,
                    "updated_at": fetched_at,
                    "source": client.SOURCE,
                }
                history.append(
                    {
                        "id": f"{pair}_{timestamp}",
                        "from_currency": from_code,
                        "to_currency": to_code,
                        "rate": rate,
                        "timestamp": timestamp,
                        "source": client.SOURCE,
                        "meta": client.details[pair]["meta"],
                    }
                )

        if not pairs:
            raise ApiRequestError("не удалось получить курсы ни из одного источника")

        last_refresh = fetched_at
        self.logger.info(f"Writing {len(pairs)} rates to data/rates.json...")
        self.storage.save_rates(pairs, last_refresh)
        self.storage.save_history(history)
        return {"updated": len(pairs), "last_refresh": last_refresh, "errors": errors}


def create_updater(source: str | None = None) -> RatesUpdater:
    """Собирает RatesUpdater; source — 'coingecko', 'exchangerate' или None (все)."""
    config = ParserConfig()
    clients = {
        "coingecko": CoinGeckoClient(config),
        "exchangerate": ExchangeRateApiClient(config),
    }
    if source is None:
        selected = list(clients.values())
    elif source in clients:
        selected = [clients[source]]
    else:
        raise ValueError(
            f"Неизвестный источник '{source}'. Доступно: coingecko, exchangerate"
        )
    return RatesUpdater(selected, RatesStorage())
