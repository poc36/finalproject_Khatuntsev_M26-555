"""SettingsLoader — единая точка конфигурации (Singleton)."""

import tomllib
from typing import Any

# Значения по умолчанию; переопределяются секцией [tool.valutatrade] в pyproject.toml
DEFAULTS = {
    "data_dir": "data",
    "users_file": "data/users.json",
    "portfolios_file": "data/portfolios.json",
    "rates_file": "data/rates.json",
    "history_file": "data/exchange_rates.json",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "log_dir": "logs",
    "log_file": "logs/actions.log",
    "log_level": "INFO",
    "log_format": "%(levelname)s %(asctime)s %(message)s",
    "log_max_bytes": 1_000_000,
    "log_backup_count": 3,
    "parser_log_file": "logs/parser.log",
    "parser_interval_seconds": 300,
}


class SettingsLoader:
    """Загружает и кеширует конфигурацию проекта.

    Singleton реализован через __new__: это самый простой и читаемый способ
    (как в примере ShopConfig из курса) — метакласс здесь избыточен.
    Модуль импортируется один раз, а __new__ всегда возвращает один и тот же
    объект, поэтому лишних экземпляров не появляется.
    """

    _instance = None

    def __new__(cls, config_path: str = "pyproject.toml"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config_path = config_path
            cls._instance._settings = {}
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        """Перечитывает конфигурацию из pyproject.toml."""
        settings = dict(DEFAULTS)
        try:
            with open(self._config_path, "rb") as f:
                data = tomllib.load(f)
            settings.update(data.get("tool", {}).get("valutatrade", {}))
        except FileNotFoundError:
            pass  # работаем на значениях по умолчанию
        self._settings = settings

    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает значение настройки по ключу."""
        return self._settings.get(key, default)
