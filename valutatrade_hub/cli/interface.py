"""Командный интерфейс (CLI): разбор команд и вызов бизнес-логики."""

import shlex

from valutatrade_hub.core import usecases

HELP_TEXT = """Команды:
  register --username <имя> --password <пароль>
  login --username <имя> --password <пароль>
  show-portfolio [--base <валюта>]
  buy --currency <код> --amount <количество>
  sell --currency <код> --amount <количество>
  get-rate --from <валюта> --to <валюта>
  help
  exit"""


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


def run() -> None:
    """Главный цикл: читает команды и выводит результат."""
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

            match command:
                case "register":
                    username, password = require(args, "username", "password")
                    print(usecases.register(username, password))
                case "login":
                    username, password = require(args, "username", "password")
                    current_user = usecases.login(username, password)
                    print(f"Вы вошли как '{current_user.username}'")
                case "show-portfolio":
                    base = args.get("base", "USD")
                    print(usecases.show_portfolio(current_user, base))
                case "buy":
                    currency, amount = require(args, "currency", "amount")
                    print(usecases.buy(current_user, currency, amount))
                case "sell":
                    currency, amount = require(args, "currency", "amount")
                    print(usecases.sell(current_user, currency, amount))
                case "get-rate":
                    from_code, to_code = require(args, "from", "to")
                    print(usecases.get_rate(from_code, to_code))
                case "help":
                    print(HELP_TEXT)
                case "exit":
                    break
                case _:
                    print(f"Неизвестная команда '{command}'. Введите help.")
        except ValueError as error:
            print(error)
