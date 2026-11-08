"""Бизнес-логика команд: register, login, show-portfolio, buy, sell, get-rate."""

import hashlib
import os
from datetime import datetime

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.core.models import (
    EXCHANGE_RATES,
    MIN_PASSWORD_LENGTH,
    Portfolio,
    User,
    Wallet,
)
from valutatrade_hub.core.utils import convert, validate_amount, validate_currency_code
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

# Синглтоны: одна конфигурация и один доступ к хранилищу на всё приложение
settings = SettingsLoader()
db = DatabaseManager()


# ---------- пользователи ----------


def _user_from_dict(data: dict) -> User:
    """Создаёт объект User из записи users.json."""
    return User(
        user_id=data["user_id"],
        username=data["username"],
        hashed_password=data["hashed_password"],
        salt=data["salt"],
        registration_date=datetime.fromisoformat(data["registration_date"]),
    )


@log_action("REGISTER")
def register(username: str, password: str) -> int:
    """Регистрирует пользователя, создаёт пустой портфель. Возвращает user_id."""
    if not username or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")

    users = db.read("users")
    if any(u["username"] == username for u in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = max((u["user_id"] for u in users), default=0) + 1
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    users.append(
        {
            "user_id": user_id,
            "username": username,
            "hashed_password": hashed,
            "salt": salt,
            "registration_date": datetime.now().isoformat(timespec="seconds"),
        }
    )
    db.write("users", users)

    portfolios = db.read("portfolios")
    portfolios.append({"user_id": user_id, "wallets": {}})
    db.write("portfolios", portfolios)
    return user_id


@log_action("LOGIN")
def login(username: str, password: str) -> User:
    """Находит пользователя и проверяет пароль."""
    for data in db.read("users"):
        if data["username"] == username:
            user = _user_from_dict(data)
            if not user.verify_password(password):
                raise ValueError("Неверный пароль")
            return user
    raise ValueError(f"Пользователь '{username}' не найден")


def _require_login(user_id: int | None) -> None:
    """Проверяет, что пользователь вошёл в систему."""
    if user_id is None:
        raise ValueError("Сначала выполните login")


# ---------- портфели: чтение → модификация → запись ----------


def _load_portfolio(user_id: int) -> Portfolio:
    """Загружает портфель пользователя."""
    for data in db.read("portfolios"):
        if data["user_id"] == user_id:
            wallets = {
                code: Wallet(code, info["balance"])
                for code, info in data["wallets"].items()
            }
            return Portfolio(user_id, wallets)
    return Portfolio(user_id, {})


def _save_portfolio(user_id: int, portfolio: Portfolio) -> None:
    """Сохраняет портфель пользователя."""
    portfolios = [p for p in db.read("portfolios") if p["user_id"] != user_id]
    portfolios.append(
        {
            "user_id": user_id,
            "wallets": {
                code: {"balance": wallet.balance}
                for code, wallet in portfolio.wallets.items()
            },
        }
    )
    db.write("portfolios", portfolios)


# ---------- курсы ----------


def _fetch_rate_to_usd(code: str) -> float:
    """Заглушка внешнего API курсов (до подключения Parser Service)."""
    if code not in EXCHANGE_RATES:
        raise ApiRequestError(f"нет данных по валюте {code}")
    return EXCHANGE_RATES[code]


def _rate_to_usd(code: str, cache: dict, now: datetime) -> tuple[float, datetime]:
    """Курс code→USD из кеша, если он свежий, иначе — из API с обновлением кеша."""
    base = "USD"
    if code == base:
        return 1.0, now
    key = f"{code}_{base}"
    entry = cache.get(key)
    if entry:
        updated = datetime.fromisoformat(entry["updated_at"])
        if (now - updated).total_seconds() < settings.get("rates_ttl_seconds"):
            return entry["rate"], updated
    rate = _fetch_rate_to_usd(code)
    cache[key] = {"rate": rate, "updated_at": now.isoformat(timespec="seconds")}
    cache["source"] = "ExchangeRatesStub"
    cache["last_refresh"] = now.isoformat(timespec="seconds")
    return rate, now


def get_rate(from_code: str, to_code: str) -> tuple[float, str]:
    """Курс from→to и время обновления. Неизвестный код — CurrencyNotFoundError."""
    from_code = get_currency(validate_currency_code(from_code)).code
    to_code = get_currency(validate_currency_code(to_code)).code

    cache = db.read("rates")
    now = datetime.now()
    from_rate, from_time = _rate_to_usd(from_code, cache, now)
    to_rate, to_time = _rate_to_usd(to_code, cache, now)
    db.write("rates", cache)

    updated_at = min(from_time, to_time).strftime("%Y-%m-%d %H:%M:%S")
    return from_rate / to_rate, updated_at


# ---------- операции с портфелем ----------


def show_portfolio(user: User | None, base: str | None = None) -> dict:
    """Кошельки пользователя и их стоимость в базовой валюте."""
    _require_login(user.user_id if user else None)
    base = validate_currency_code(base or settings.get("default_base_currency"))
    try:
        get_currency(base)
    except CurrencyNotFoundError:
        raise ValueError(f"Неизвестная базовая валюта '{base}'") from None

    portfolio = _load_portfolio(user.user_id)
    rows = []
    for code, wallet in portfolio.wallets.items():
        rate, _ = get_rate(code, base)
        rows.append((code, wallet.balance, convert(wallet.balance, rate)))
    return {
        "username": user.username,
        "base": base,
        "rows": rows,
        "total": sum(value for _, _, value in rows),
    }


@log_action("BUY", verbose=True)
def buy(user_id: int | None, currency_code: str, amount) -> dict:
    """Покупка валюты: увеличивает баланс кошелька (создаёт его при отсутствии)."""
    _require_login(user_id)
    amount = validate_amount(amount)
    code = get_currency(validate_currency_code(currency_code)).code
    rate, _ = get_rate(code, "USD")

    portfolio = _load_portfolio(user_id)
    wallet = portfolio.get_wallet(code) or portfolio.add_currency(code)
    before = wallet.balance
    wallet.deposit(amount)
    _save_portfolio(user_id, portfolio)

    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "base": "USD",
        "before": before,
        "after": wallet.balance,
        "value": convert(amount, rate),
    }


@log_action("SELL", verbose=True)
def sell(user_id: int | None, currency_code: str, amount) -> dict:
    """Продажа валюты. Нехватка средств — InsufficientFundsError."""
    _require_login(user_id)
    amount = validate_amount(amount)
    code = get_currency(validate_currency_code(currency_code)).code

    portfolio = _load_portfolio(user_id)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{code}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        )
    before = wallet.balance
    wallet.withdraw(amount)
    rate, _ = get_rate(code, "USD")
    _save_portfolio(user_id, portfolio)

    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "base": "USD",
        "before": before,
        "after": wallet.balance,
        "value": convert(amount, rate),
    }
