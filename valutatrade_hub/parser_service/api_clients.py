"""Клиенты внешних API курсов с единым интерфейсом fetch_rates()."""

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


def _utc_iso(unix_time: float | None) -> str:
    """Время в формате ISO UTC: 2025-10-10T12:00:00Z."""
    moment = (
        datetime.fromtimestamp(unix_time, timezone.utc)
        if unix_time
        else datetime.now(timezone.utc)
    )
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class BaseApiClient(ABC):
    """Базовый клиент: fetch_rates() -> {"BTC_USD": 59337.21, ...}."""

    SOURCE = "base"

    def __init__(self, config: ParserConfig):
        self.config = config
        # Подробности последнего запроса: время, исходный ID, метаданные ответа
        self.details: dict[str, dict] = {}

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Возвращает курсы в стандартном формате."""

    def _get(self, url: str, params: dict | None = None) -> tuple[dict, dict]:
        """GET-запрос с обработкой ошибок. Возвращает (json, meta)."""
        start = time.monotonic()
        try:
            response = requests.get(
                url, params=params, timeout=self.config.REQUEST_TIMEOUT
            )
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(f"сетевая ошибка ({error})") from error

        if response.status_code == 429:
            raise ApiRequestError("превышен лимит запросов (429)")
        if response.status_code in (401, 403):
            raise ApiRequestError("неверный API-ключ")
        if response.status_code != 200:
            raise ApiRequestError(f"код ответа {response.status_code}")
        try:
            data = response.json()
        except ValueError as error:
            raise ApiRequestError("ответ не в формате JSON") from error

        meta = {
            "request_ms": round((time.monotonic() - start) * 1000),
            "status_code": response.status_code,
            "etag": response.headers.get("ETag"),
        }
        return data, meta

    @staticmethod
    def _check_rate(value, pair: str) -> float:
        """Проверяет, что курс — положительное число."""
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ApiRequestError(f"некорректный курс для {pair}: {value!r}")
        return float(value)


class CoinGeckoClient(BaseApiClient):
    """Курсы криптовалют из CoinGecko."""

    SOURCE = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        base = self.config.BASE_CURRENCY
        ids = [self.config.CRYPTO_ID_MAP[c] for c in self.config.CRYPTO_CURRENCIES]
        params = {
            "ids": ",".join(ids),
            "vs_currencies": base.lower(),
            "include_last_updated_at": "true",
        }
        data, meta = self._get(self.config.COINGECKO_URL, params)

        rates = {}
        self.details = {}
        for code in self.config.CRYPTO_CURRENCIES:
            raw_id = self.config.CRYPTO_ID_MAP[code]
            item = data.get(raw_id)
            if not item or base.lower() not in item:
                raise ApiRequestError(f"нет данных для {code}")
            pair = f"{code}_{base}"
            rates[pair] = self._check_rate(item[base.lower()], pair)
            self.details[pair] = {
                "timestamp": _utc_iso(item.get("last_updated_at")),
                "meta": {"raw_id": raw_id, **meta},
            }
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Курсы фиатных валют из ExchangeRate-API."""

    SOURCE = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, float]:
        key = self.config.EXCHANGERATE_API_KEY
        if not key:
            raise ApiRequestError("не задан ключ EXCHANGERATE_API_KEY")
        base = self.config.BASE_CURRENCY
        url = f"{self.config.EXCHANGERATE_API_URL}/{key}/latest/{base}"
        data, meta = self._get(url)

        if data.get("result") != "success":
            reason = data.get("error-type", "неизвестная ошибка")
            raise ApiRequestError(reason)

        timestamp = _utc_iso(data.get("time_last_update_unix"))
        # Реальный API v6 кладёт курсы в conversion_rates, в примере задания — rates
        raw_rates = data.get("conversion_rates") or data.get("rates") or {}
        rates = {}
        self.details = {}
        for code in self.config.FIAT_CURRENCIES:
            if code not in raw_rates:
                raise ApiRequestError(f"нет данных для {code}")
            # API отдаёт «сколько code за 1 USD», а нам нужен курс code→USD
            per_usd = self._check_rate(raw_rates[code], f"{base}_{code}")
            pair = f"{code}_{base}"
            rates[pair] = 1 / per_usd
            self.details[pair] = {
                "timestamp": timestamp,
                "meta": {"raw_id": code, **meta},
            }
        return rates
