"""Бизнес-логика команд: register, login, show-portfolio, buy, sell, get-rate."""

import hashlib
import os
from datetime import datetime, timezone

from valutatrade_hub.core.currencies import CryptoCurrency, get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.core.models import (
    MIN_PASSWORD_LENGTH,
    Portfolio,
    User,
    Wallet,
)
from valutatrade_hub.core.utils import convert, validate_amount, validate_currency_code
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import create_updater

# Синглтоны: одна конфигурация и один доступ к хранилищу на всё приложение
settings = SettingsLoader()
db = DatabaseManager()
storage = RatesStorage()


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


def _parse_time(value: str) -> datetime:
    """ISO-время (в т.ч. с 'Z') в datetime с часовым поясом UTC."""
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _fresh_pair(pairs: dict, code: str) -> dict | None:
    """Пара code_USD из кеша, если она моложе TTL, иначе None."""
    entry = pairs.get(f"{code}_USD")
    if entry is None:
        return None
    age = datetime.now(timezone.utc) - _parse_time(entry["updated_at"])
    return entry if age.total_seconds() < settings.get("rates_ttl_seconds") else None


def get_rate(from_code: str, to_code: str) -> tuple[float, str]:
    """Курс from→to и время обновления из кеша rates.json.

    Неизвестный код — CurrencyNotFoundError. Если курс устарел (старше TTL),
    запускает Parser Service; если обновить не удалось — ApiRequestError.
    """
    from_code = get_currency(validate_currency_code(from_code)).code
    to_code = get_currency(validate_currency_code(to_code)).code
    codes = [c for c in (from_code, to_code) if c != "USD"]

    pairs = storage.load_rates()["pairs"]
    if any(_fresh_pair(pairs, c) is None for c in codes):
        create_updater().run_update()  # может бросить ApiRequestError
        pairs = storage.load_rates()["pairs"]

    rates, times = {"USD": 1.0}, []
    for code in codes:
        entry = _fresh_pair(pairs, code)
        if entry is None:
            raise ApiRequestError(f"курс {code}→USD недоступен")
        rates[code] = entry["rate"]
        times.append(_parse_time(entry["updated_at"]))

    updated = min(times) if times else datetime.now(timezone.utc)
    return rates[from_code] / rates[to_code], updated.strftime("%Y-%m-%d %H:%M:%S")


def show_rates(
    currency: str | None = None, top: int | None = None, base: str | None = None
) -> dict:
    """Курсы из локального кеша с фильтрами --currency, --top, --base."""
    cache = storage.load_rates()
    pairs = cache["pairs"]
    if not pairs:
        raise ValueError(
            "Локальный кеш курсов пуст. "
            "Выполните 'update-rates', чтобы загрузить данные."
        )

    base = get_currency(validate_currency_code(base)).code if base else "USD"
    if base == "USD":
        base_rate = 1.0
    elif f"{base}_USD" in pairs:
        base_rate = pairs[f"{base}_USD"]["rate"]
    else:
        raise ValueError(f"Курс для '{base}' не найден в кеше.")

    rows = []
    for pair, entry in pairs.items():
        code = pair.split("_")[0]
        if code != base:
            rows.append(
                (code, entry["rate"] / base_rate, entry["updated_at"], entry["source"])
            )
    if base != "USD":
        base_entry = pairs[f"{base}_USD"]
        rows.append(
            ("USD", 1 / base_rate, base_entry["updated_at"], base_entry["source"])
        )

    if currency:
        code = validate_currency_code(currency)
        rows = [row for row in rows if row[0] == code]
        if not rows:
            raise ValueError(f"Курс для '{code}' не найден в кеше.")
    if top:
        crypto = [r for r in rows if isinstance(get_currency(r[0]), CryptoCurrency)]
        rows = sorted(crypto, key=lambda r: r[1], reverse=True)[: int(top)]
    else:
        rows.sort()

    return {
        "last_refresh": cache["last_refresh"],
        "rows": [
            (f"{code}_{base}", rate, updated_at, source)
            for code, rate, updated_at, source in rows
        ],
    }


def update_rates(source: str | None = None) -> dict:
    """Немедленное обновление курсов через Parser Service."""
    return create_updater(source).run_update()


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
