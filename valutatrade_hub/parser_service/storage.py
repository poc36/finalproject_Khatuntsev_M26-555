"""Хранилище Parser Service: история (exchange_rates.json) и кеш (rates.json)."""

from datetime import datetime, timezone

from valutatrade_hub.infra.database import DatabaseManager


def _parse_time(value: str) -> datetime:
    """ISO-время (в т.ч. с 'Z') в datetime с часовым поясом UTC."""
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


class RatesStorage:
    """Чтение и атомарная запись файлов курсов через DatabaseManager."""

    def __init__(self):
        self._db = DatabaseManager()

    def load_rates(self) -> dict:
        """Текущий кеш: {"pairs": {...}, "last_refresh": ...}."""
        data = self._db.read("rates")
        return data if "pairs" in data else {"pairs": {}, "last_refresh": None}

    def save_history(self, records: list[dict]) -> int:
        """Добавляет записи в историю без дублей по id. Возвращает число новых."""
        history = self._db.read("history")
        known_ids = {record["id"] for record in history}
        new_records = [r for r in records if r["id"] not in known_ids]
        if new_records:
            self._db.write("history", history + new_records)
        return len(new_records)

    def save_rates(self, pairs: dict[str, dict], last_refresh: str) -> None:
        """Обновляет кеш: значение пары заменяется, только если оно свежее."""
        cache = self.load_rates()
        for pair, entry in pairs.items():
            current = cache["pairs"].get(pair)
            if current is None or _parse_time(entry["updated_at"]) >= _parse_time(
                current["updated_at"]
            ):
                cache["pairs"][pair] = entry
        cache["last_refresh"] = last_refresh
        self._db.write("rates", cache)
