"""Конфигурация Parser Service: API, списки валют, пути, сетевые параметры."""

import os
from dataclasses import dataclass, field

from valutatrade_hub.infra.settings import SettingsLoader

ENV_FILE = ".env"  # локальный файл с ключом, не отслеживается git


def _load_api_key() -> str | None:
    """Ключ ExchangeRate-API из переменной окружения или файла .env."""
    key = os.getenv("EXCHANGERATE_API_KEY")
    if key:
        return key
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                name, sep, value = line.strip().partition("=")
                if sep and name.strip() == "EXCHANGERATE_API_KEY":
                    return value.strip()
    except FileNotFoundError:
        pass
    return None


@dataclass
class ParserConfig:
    """Все изменяемые параметры парсера в одном месте."""

    # Ключ загружается из окружения, а не хранится в коде
    EXCHANGERATE_API_KEY: str | None = field(default_factory=_load_api_key)

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Списки валют
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    # Пути (из общей конфигурации проекта)
    RATES_FILE_PATH: str = field(
        default_factory=lambda: SettingsLoader().get("rates_file")
    )
    HISTORY_FILE_PATH: str = field(
        default_factory=lambda: SettingsLoader().get("history_file")
    )

    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10
