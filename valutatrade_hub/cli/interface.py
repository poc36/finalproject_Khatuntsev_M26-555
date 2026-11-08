"""Командный интерфейс (CLI): разбор команд и вызов бизнес-логики."""

import shlex

from valutatrade_hub.core import usecases
from valutatrade_hub.core.currencies import supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.logging_config import setup_logging

HELP_TEXT = """Команды:
  register --username <имя> --password <пароль>
  login --username <имя> --password <пароль>
  show-portfolio [--base <валюта>]
  buy --currency <код> --amount <количество>
  sell --currency <код> --amount <количество>
  get-rate --from <валюта> --to <валюта>
  help
  exit"""

CRYPTO_CURRENCIES = {"BTC", "ETH"}


def parse_args(tokens: list[str]) -> dict[str, str]:
    """Превращает ['--username', 'alice'] в {'username': 'alice'}."""
    args = {}
    i = 0
    while i < len(tokens):
        key = tokens[i]
        if not key.startswith("--") or i + 1 >= len(tokens):
            raise ValueError(f"Некорректный аргумент: {key}")
        args[key[2:]] = tokens[i + 1]
        i += 2
    return args


def require(args: dict[str, str], *names: str) -> list[str]:
    """Возвращает значения обязательных аргументов."""
    missing = [name for name in names if name not in args]
    if missing:
        raise ValueError(f"Не указан аргумент --{missing[0]}")
    return [args[name] for name in names]


def fmt_amount(code: str, value: float) -> str:
    """Криптовалюты — 4 знака после запятой, остальные — 2."""
    return f"{value:.4f}" if code in CRYPTO_CURRENCIES else f"{value:.2f}"


def fmt_rate(rate: float) -> str:
    """Курс без лишних нулей."""
    return f"{rate:.8f}".rstrip("0").rstrip(".")


def print_portfolio(data: dict) -> None:
    """Выводит портфель."""
    if not data["rows"]:
        print(f"У пользователя '{data['username']}' пока нет кошельков")
        return
    base = data["base"]
    print(f"Портфель пользователя '{data['username']}' (база: {base}):")
    for code, balance, value in data["rows"]:
        print(f"- {code}: {fmt_amount(code, balance)}  → {value:,.2f} {base}")
    print("---------------------------------")
    print(f"ИТОГО: {data['total']:,.2f} {base}")


def print_trade(title: str, value_title: str, data: dict) -> None:
    """Выводит результат покупки или продажи."""
    code, base = data["currency"], data["base"]
    print(
        f"{title}: {data['amount']:.4f} {code} по курсу "
        f"{data['rate']:.2f} {base}/{code}"
    )
    print("Изменения в портфеле:")
    print(f"- {code}: было {data['before']:.4f} → стало {data['after']:.4f}")
    print(f"{value_title}: {data['value']:,.2f} {base}")


def run() -> None:
    """Главный цикл: читает команды и выводит результат."""
    setup_logging()
    print("ValutaTrade Hub. Введите help для списка команд.")
    current_user = None

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue

        try:
            command, *tokens = shlex.split(line)
            args = parse_args(tokens)
            user_id = current_user.user_id if current_user else None

            match command:
                case "register":
                    username, password = require(args, "username", "password")
                    new_id = usecases.register(username, password)
                    print(
                        f"Пользователь '{username}' зарегистрирован (id={new_id}). "
                        f"Войдите: login --username {username} --password ****"
                    )
                case "login":
                    username, password = require(args, "username", "password")
                    current_user = usecases.login(username, password)
                    print(f"Вы вошли как '{current_user.username}'")
                case "show-portfolio":
                    print_portfolio(
                        usecases.show_portfolio(current_user, args.get("base"))
                    )
                case "buy":
                    currency, amount = require(args, "currency", "amount")
                    data = usecases.buy(user_id, currency, amount)
                    print_trade(
                        "Покупка выполнена", "Оценочная стоимость покупки", data
                    )
                case "sell":
                    currency, amount = require(args, "currency", "amount")
                    data = usecases.sell(user_id, currency, amount)
                    print_trade("Продажа выполнена", "Оценочная выручка", data)
                case "get-rate":
                    from_code, to_code = require(args, "from", "to")
                    rate, updated_at = usecases.get_rate(from_code, to_code)
                    f, t = from_code.upper(), to_code.upper()
                    print(f"Курс {f}→{t}: {fmt_rate(rate)} (обновлено: {updated_at})")
                    print(f"Обратный курс {t}→{f}: {fmt_rate(1 / rate)}")
                case "help":
                    print(HELP_TEXT)
                case "exit":
                    break
                case _:
                    print(f"Неизвестная команда '{command}'. Введите help.")
        except InsufficientFundsError as error:
            print(error)
        except CurrencyNotFoundError as error:
            print(error)
            print(f"Поддерживаемые валюты: {', '.join(supported_codes())}")
        except ApiRequestError as error:
            print(error)
            print("Повторите попытку позже или проверьте подключение к сети.")
        except ValueError as error:
            print(error)
