"""DatabaseManager — абстракция над JSON-хранилищем (Singleton)."""

import json
import os
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Чтение и безопасная запись JSON-файлов из data/.

    Singleton через __new__ (по той же причине, что и SettingsLoader).
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            settings = SettingsLoader()
            cls._instance._files = {
                "users": settings.get("users_file"),
                "portfolios": settings.get("portfolios_file"),
                "rates": settings.get("rates_file"),
            }
        return cls._instance

    def read(self, name: str) -> Any:
        """Читает данные: 'users', 'portfolios' или 'rates'."""
        default = {} if name == "rates" else []
        try:
            with open(self._files[name], encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default

    def write(self, name: str, data: Any) -> None:
        """Записывает данные атомарно: во временный файл, затем подмена."""
        path = self._files[name]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
