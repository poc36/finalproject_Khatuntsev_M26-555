"""Классы предметной области: пользователь, кошелёк, портфель."""

import hashlib
from datetime import datetime

from valutatrade_hub.core.exceptions import InsufficientFundsError

# Фиксированные курсы к USD (заглушка до подключения Parser Service)
EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 1.0786,
    "RUB": 0.01016,
    "BTC": 59337.21,
    "ETH": 3720.00,
}

MIN_PASSWORD_LENGTH = 4


class User:
    """Пользователь системы."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ):
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    def _hash(self, password: str) -> str:
        """Односторонний псевдо-хеш sha256(password + salt)."""
        return hashlib.sha256((password + self._salt).encode("utf-8")).hexdigest()

    @property
    def user_id(self) -> int:
        """Идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value

    @property
    def hashed_password(self) -> str:
        """Пароль в зашифрованном виде."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Соль пользователя."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Дата регистрации."""
        return self._registration_date

    def get_user_info(self) -> str:
        """Возвращает информацию о пользователе (без пароля)."""
        date = self._registration_date.strftime("%Y-%m-%d %H:%M:%S")
        return f"ID: {self._user_id}, имя: {self._username}, регистрация: {date}"

    def change_password(self, new_password: str) -> None:
        """Изменяет пароль, сохраняя его хеш."""
        if len(new_password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов"
            )
        self._hashed_password = self._hash(new_password)

    def verify_password(self, password: str) -> bool:
        """Проверяет введённый пароль на совпадение."""
        return self._hash(password) == self._hashed_password


class Wallet:
    """Кошелёк пользователя для одной конкретной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code
        self.balance = balance

    @property
    def balance(self) -> float:
        """Текущий баланс."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    @staticmethod
    def _check_amount(amount: float) -> None:
        """Проверяет, что amount — положительное число."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("'amount' должен быть положительным числом")
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")

    def deposit(self, amount: float) -> None:
        """Пополнение баланса."""
        self._check_amount(amount)
        self.balance = self._balance + amount

    def withdraw(self, amount: float) -> None:
        """Снятие средств, если баланс позволяет."""
        self._check_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError(self._balance, amount, self.currency_code)
        self.balance = self._balance - amount

    def get_balance_info(self) -> str:
        """Информация о текущем балансе."""
        return f"{self.currency_code}: {self._balance:.4f}"


class Portfolio:
    """Управление всеми кошельками одного пользователя."""

    def __init__(
        self,
        user_id: int,
        wallets: dict[str, Wallet] | None = None,
        user: User | None = None,
    ):
        self._user_id = user_id
        self._wallets = wallets if wallets is not None else {}
        self._user = user

    @property
    def user(self) -> User | None:
        """Объект пользователя (без возможности перезаписи)."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Копия словаря кошельков."""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавляет новый кошелёк в портфель, если его ещё нет."""
        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк '{currency_code}' уже существует")
        wallet = Wallet(currency_code)
        self._wallets[currency_code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Возвращает объект Wallet по коду валюты."""
        return self._wallets.get(currency_code)

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Общая стоимость всех валют в базовой валюте."""
        if base_currency not in EXCHANGE_RATES:
            raise ValueError(f"Неизвестная базовая валюта '{base_currency}'")
        total_usd = sum(
            wallet.balance * EXCHANGE_RATES[code]
            for code, wallet in self._wallets.items()
        )
        return total_usd / EXCHANGE_RATES[base_currency]
