"""Вспомогательные функции: работа с JSON-файлами и валидация ввода."""

import json
import os

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PORTFOLIOS_FILE = os.path.join(DATA_DIR, "portfolios.json")
RATES_FILE = os.path.join(DATA_DIR, "rates.json")


def load_json(filepath: str, default):
    """Загружает данные из JSON-файла. Если файла нет — возвращает default."""
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(filepath: str, data) -> None:
    """Сохраняет данные в JSON-файл."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def validate_currency_code(code: str) -> str:
    """Проверяет код валюты: непустая строка, возвращает в верхнем регистре."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    return code.strip().upper()


def validate_amount(value) -> float:
    """Проверяет, что amount — положительное число, и возвращает float."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("'amount' должен быть положительным числом") from None
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return amount
