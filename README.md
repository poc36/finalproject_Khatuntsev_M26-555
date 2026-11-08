# ValutaTrade Hub

Консольная платформа для симуляции торговли валютами: регистрация пользователей,
виртуальный портфель фиатных и криптовалют, покупка и продажа, актуальные курсы.

Система состоит из двух сервисов:

- **Core Service** — CLI, пользователи, портфели, операции buy/sell, курсы из локального кеша;
- **Parser Service** — получает курсы из CoinGecko (криптовалюты) и ExchangeRate-API
  (фиатные валюты) и сохраняет их в кеш и историю.

## Демонстрация

[![asciicast](https://asciinema.org/a/xDSNbD4ARIWrSJic.png)](https://asciinema.org/a/xDSNbD4ARIWrSJic)

## Структура проекта

```
finalproject_Khatuntsev_M26-555/
├── data/
│   ├── users.json              # пользователи
│   ├── portfolios.json         # портфели и кошельки
│   ├── rates.json              #  кеш актуальных курсов
│   └── exchange_rates.json     # история курсов
├── valutatrade_hub/
│   ├── logging_config.py       # настройка логов
│   ├── decorators.py           # @log_action
│   ├── core/                   # currencies, exceptions, models, usecases, utils
│   ├── infra/                  # settings (SettingsLoader), database (DatabaseManager)
│   ├── parser_service/         # config, api_clients, updater, storage, scheduler
│   └── cli/                    # interface — команды CLI
├── main.py
└── pyproject.toml
```

## Установка

```bash
git clone https://github.com/poc36/finalproject_Khatuntsev_M26-555.git
cd finalproject_Khatuntsev_M26-555
uv sync
```

## Запуск

```bash
uv run project
```

Или в активированном виртуальном окружении (`source .venv/Scripts/activate`
в Windows, `source .venv/bin/activate` в Linux/macOS):

```bash
project
```

```bash
python main.py
```

## Команды

| Команда | Назначение |
|---|---|
| `register --username <имя> --password <пароль>` | регистрация |
| `login --username <имя> --password <пароль>` | вход |
| `show-portfolio [--base <валюта>]` | портфель и итоговая стоимость |
| `buy --currency <код> --amount <количество>` | покупка валюты |
| `sell --currency <код> --amount <количество>` | продажа валюты |
| `get-rate --from <валюта> --to <валюта>` | курс одной валюты к другой |
| `update-rates [--source coingecko\|exchangerate]` | обновить курсы |
| `show-rates [--currency <код>] [--top <N>] [--base <валюта>]` | курсы из кеша |

Поддерживаемые валюты: USD, EUR, GBP, RUB, BTC, ETH, SOL.

### Примеры

```
> register --username alice --password 1234
Пользователь 'alice' зарегистрирован (id=1). Войдите: login --username alice --password ****

> login --username alice --password 1234
Вы вошли как 'alice'

> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC по курсу 59337.21 USD/BTC
Изменения в портфеле:
- BTC: было 0.0000 → стало 0.0500
Оценочная стоимость покупки: 2,966.86 USD

> sell --currency BTC --amount 1
Недостаточно средств: доступно 0.0500 BTC, требуется 1.0000 BTC

> get-rate --from USD --to BTC
Курс USD→BTC: 0.00001685 (обновлено: 2025-10-10 12:00:00)
Обратный курс BTC→USD: 59337.21
```

## Кеш курсов и TTL

- `data/rates.json` — последние курсы по парам (`BTC_USD`, `EUR_USD`, …) с временем
  обновления и источником. Core Service читает курсы отсюда.
- `data/exchange_rates.json` — история всех полученных курсов.
- TTL — `rates_ttl_seconds` в секции `[tool.valutatrade]` файла `pyproject.toml`
  (по умолчанию 300 секунд). Если курс устарел, программа сама запускает обновление;
  если обновить не удалось, выводит сообщение с предложением повторить позже.

## Parser Service

Получите ключ на https://www.exchangerate-api.com/ и сохраните его в переменной
окружения или в файле `.env` в корне проекта (файл в `.gitignore`):

```
EXCHANGERATE_API_KEY=ваш_ключ
```

CoinGecko работает без ключа.

Обновление курсов — команда `update-rates`. Периодическое обновление:

```bash
uv run python -m valutatrade_hub.parser_service.scheduler
```
