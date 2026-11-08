"""Вспомогательные функции: валидация ввода и конвертация."""


def validate_currency_code(code: str) -> str:
    """Проверяет формат кода валюты и возвращает его в верхнем регистре."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    code = code.strip().upper()
    if not 2 <= len(code) <= 5 or " " in code:
        raise ValueError(f"Некорректный код валюты '{code}'")
    return code


def validate_amount(value) -> float:
    """Проверяет, что amount — положительное число, и возвращает float."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("'amount' должен быть положительным числом") from None
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return amount


def convert(amount: float, rate: float) -> float:
    """Пересчитывает сумму по курсу."""
    return amount * rate
