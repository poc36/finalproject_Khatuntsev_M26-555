"""Бизнес-логика команд: register, login, show-portfolio, buy, sell, get-rate."""

import hashlib
import os
from datetime import datetime

from valutatrade_hub.core.models import (
    EXCHANGE_RATES,
    MIN_PASSWORD_LENGTH,
    Portfolio,
    User,
    Wallet,
)
from valutatrade_hub.core.utils import (
    PORTFOLIOS_FILE,
    RATES_FILE,
    USERS_FILE,
    load_json,
    save_json,
    validate_amount,
    validate_currency_code,
)

RATES_TTL_SECONDS = 300  # курс считается свежим 5 минут
BASE_CURRENCY = "USD"
CRYPTO_CURRENCIES = {"BTC", "ETH"}


# ---------- пользователи ----------


def _load_users() -> list[dict]:
    """Список пользователей из users.json."""
    return load_json(USERS_FILE, [])


def _user_from_dict(data: dict) -> User:
    """Создаёт объект User из записи users.json."""
    return User(
        user_id=data["user_id"],
        username=data["username"],
        hashed_password=data["hashed_password"],
        salt=data["salt"],
        registration_date=datetime.fromisoformat(data["registration_date"]),
    )


def register(username: str, password: str) -> str:
    """Регистрирует нового пользователя и создаёт ему пустой портфель."""
    if not username or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")

    users = _load_users()
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
    save_json(USERS_FILE, users)

    portfolios = load_json(PORTFOLIOS_FILE, [])
    portfolios.append({"user_id": user_id, "wallets": {}})
    save_json(PORTFOLIOS_FILE, portfolios)

    return (
        f"Пользователь '{username}' зарегистрирован (id={user_id}). "
        f"Войдите: login --username {username} --password ****"
    )


def login(username: str, password: str) -> User:
    """Находит пользователя и проверяет пароль. Возвращает объект User."""
    for data in _load_users():
        if data["username"] == username:
            user = _user_from_dict(data)
            if not user.verify_password(password):
                raise ValueError("Неверный пароль")
            return user
    raise ValueError(f"Пользователь '{username}' не найден")


def _require_login(user: User | None) -> None:
    """Проверяет, что пользователь вошёл в систему."""
    if user is None:
        raise ValueError("Сначала выполните login")


# ---------- портфели ----------


def _load_portfolio(user: User) -> Portfolio:
    """Загружает портфель пользователя из portfolios.json."""
    for data in load_json(PORTFOLIOS_FILE, []):
        if data["user_id"] == user.user_id:
            wallets = {
                code: Wallet(code, info["balance"])
                for code, info in data["wallets"].items()
            }
            return Portfolio(user.user_id, wallets, user)
    return Portfolio(user.user_id, {}, user)


def _save_portfolio(portfolio: Portfolio) -> None:
    """Сохраняет портфель пользователя в portfolios.json."""
    record = {
        "user_id": portfolio.user.user_id,
        "wallets": {
            code: {"balance": wallet.balance}
            for code, wallet in portfolio.wallets.items()
        },
    }
    portfolios = [
        p
        for p in load_json(PORTFOLIOS_FILE, [])
        if p["user_id"] != portfolio.user.user_id
    ]
    portfolios.append(record)
    save_json(PORTFOLIOS_FILE, portfolios)


def _fmt_amount(code: str, value: float) -> str:
    """Форматирует количество валюты: криптовалюты — 4 знака, остальные — 2."""
    return f"{value:.4f}" if code in CRYPTO_CURRENCIES else f"{value:.2f}"


# ---------- курсы ----------


def get_exchange_rate(from_code: str, to_code: str) -> tuple[float, str]:
    """Единый контракт получения курса: возвращает (курс, время обновления).

    Сначала берёт курсы из кеша rates.json, если они моложе 5 минут,
    иначе — из заглушки EXCHANGE_RATES и обновляет кеш.
    """
    cache = load_json(RATES_FILE, {})
    now = datetime.now()

    def rate_to_usd(code: str) -> tuple[float, datetime] | None:
        if code == BASE_CURRENCY:
            return 1.0, now
        entry = cache.get(f"{code}_{BASE_CURRENCY}")
        if entry:
            updated = datetime.fromisoformat(entry["updated_at"])
            if (now - updated).total_seconds() < RATES_TTL_SECONDS:
                return entry["rate"], updated
        if code not in EXCHANGE_RATES:
            return None
        cache[f"{code}_{BASE_CURRENCY}"] = {
            "rate": EXCHANGE_RATES[code],
            "updated_at": now.isoformat(timespec="seconds"),
        }
        cache["source"] = "ExchangeRatesStub"
        cache["last_refresh"] = now.isoformat(timespec="seconds")
        return EXCHANGE_RATES[code], now

    from_rate = rate_to_usd(from_code)
    to_rate = rate_to_usd(to_code)
    save_json(RATES_FILE, cache)
    if from_rate is None or to_rate is None:
        raise ValueError(
            f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже."
        )
    updated_at = min(from_rate[1], to_rate[1])
    return from_rate[0] / to_rate[0], updated_at.strftime("%Y-%m-%d %H:%M:%S")


def _fmt_rate(rate: float) -> str:
    """Форматирует курс без лишних нулей."""
    return f"{rate:.8f}".rstrip("0").rstrip(".")


def get_rate(from_code: str, to_code: str) -> str:
    """Команда get-rate: курс одной валюты к другой."""
    from_code = validate_currency_code(from_code)
    to_code = validate_currency_code(to_code)
    rate, updated_at = get_exchange_rate(from_code, to_code)
    return (
        f"Курс {from_code}→{to_code}: {_fmt_rate(rate)} (обновлено: {updated_at})\n"
        f"Обратный курс {to_code}→{from_code}: {_fmt_rate(1 / rate)}"
    )


# ---------- команды с портфелем ----------


def show_portfolio(user: User | None, base: str = BASE_CURRENCY) -> str:
    """Команда show-portfolio: кошельки и итоговая стоимость в базовой валюте."""
    _require_login(user)
    base = validate_currency_code(base)
    if base not in EXCHANGE_RATES:
        raise ValueError(f"Неизвестная базовая валюта '{base}'")

    portfolio = _load_portfolio(user)
    wallets = portfolio.wallets
    if not wallets:
        return f"У пользователя '{user.username}' пока нет кошельков"

    lines = [f"Портфель пользователя '{user.username}' (база: {base}):"]
    for code, wallet in wallets.items():
        rate, _ = get_exchange_rate(code, base)
        value = wallet.balance * rate
        lines.append(
            f"- {code}: {_fmt_amount(code, wallet.balance)}  → {value:,.2f} {base}"
        )
    lines.append("---------------------------------")
    lines.append(f"ИТОГО: {portfolio.get_total_value(base):,.2f} {base}")
    return "\n".join(lines)


def buy(user: User | None, currency: str, amount) -> str:
    """Команда buy: покупка валюты (количество в штуках)."""
    _require_login(user)
    currency = validate_currency_code(currency)
    amount = validate_amount(amount)
    try:
        rate, _ = get_exchange_rate(currency, BASE_CURRENCY)
    except ValueError:
        raise ValueError(
            f"Не удалось получить курс для {currency}→{BASE_CURRENCY}"
        ) from None

    portfolio = _load_portfolio(user)
    wallet = portfolio.get_wallet(currency) or portfolio.add_currency(currency)
    before = wallet.balance
    wallet.deposit(amount)
    _save_portfolio(portfolio)

    return (
        f"Покупка выполнена: {amount:.4f} {currency} по курсу "
        f"{rate:.2f} {BASE_CURRENCY}/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {before:.4f} → стало {wallet.balance:.4f}\n"
        f"Оценочная стоимость покупки: {amount * rate:,.2f} {BASE_CURRENCY}"
    )


def sell(user: User | None, currency: str, amount) -> str:
    """Команда sell: продажа валюты."""
    _require_login(user)
    currency = validate_currency_code(currency)
    amount = validate_amount(amount)

    portfolio = _load_portfolio(user)
    wallet = portfolio.get_wallet(currency)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{currency}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        )
    before = wallet.balance
    wallet.withdraw(amount)
    rate, _ = get_exchange_rate(currency, BASE_CURRENCY)
    _save_portfolio(portfolio)

    return (
        f"Продажа выполнена: {amount:.4f} {currency} по курсу "
        f"{rate:.2f} {BASE_CURRENCY}/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {before:.4f} → стало {wallet.balance:.4f}\n"
        f"Оценочная выручка: {amount * rate:,.2f} {BASE_CURRENCY}"
    )
