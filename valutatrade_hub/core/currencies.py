"""Иерархия валют: абстрактный Currency и наследники FiatCurrency/CryptoCurrency."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактная валюта с общим интерфейсом."""

    def __init__(self, name: str, code: str):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Имя валюты не может быть пустым")
        if (
            not isinstance(code, str)
            or not 2 <= len(code) <= 5
            or " " in code
            or code != code.upper()
        ):
            raise ValueError(
                f"Некорректный код валюты '{code}': "
                "верхний регистр, 2–5 символов, без пробелов"
            )
        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление для UI и логов."""


class FiatCurrency(Currency):
    """Фиатная валюта."""

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        """[FIAT] USD — US Dollar (Issuing: United States)"""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта."""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        """[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)"""
        mcap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {mcap})"
        )


# Реестр поддерживаемых валют: код -> объект валюты
_CURRENCIES = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.5e11),
}


def get_currency(code: str) -> Currency:
    """Возвращает валюту по коду. Неизвестный код — CurrencyNotFoundError."""
    currency = _CURRENCIES.get(code.upper() if isinstance(code, str) else code)
    if currency is None:
        raise CurrencyNotFoundError(code)
    return currency


def supported_codes() -> list[str]:
    """Список кодов поддерживаемых валют."""
    return list(_CURRENCIES)
