"""Декоратор @log_action — логирование доменных операций."""

import inspect
import logging
from functools import wraps

from valutatrade_hub.logging_config import LOGGER_NAME


def log_action(action: str, verbose: bool = False):
    """Логирует операцию (BUY/SELL/REGISTER/LOGIN) на уровне INFO.

    Исключения не глотает: записывает их в лог и пробрасывает дальше.
    verbose=True добавляет состояние кошелька «было→стало».
    """

    def decorator(func):
        signature = inspect.signature(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(LOGGER_NAME)
            params = signature.bind(*args, **kwargs).arguments

            parts = [action]
            if "user_id" in params:
                parts.append(f"user_id={params['user_id']}")
            if "username" in params:
                parts.append(f"user='{params['username']}'")
            if "currency_code" in params:
                parts.append(f"currency='{str(params['currency_code']).upper()}'")
            if "amount" in params:
                try:
                    parts.append(f"amount={float(params['amount']):.4f}")
                except (TypeError, ValueError):
                    parts.append(f"amount={params['amount']!r}")

            try:
                result = func(*args, **kwargs)
            except Exception as error:
                parts.append("result=ERROR")
                parts.append(f"error_type={type(error).__name__}")
                parts.append(f'error_message="{error}"')
                logger.info(" ".join(parts))
                raise

            if isinstance(result, dict):
                if "rate" in result:
                    parts.append(f"rate={result['rate']:.2f}")
                if "base" in result:
                    parts.append(f"base='{result['base']}'")
                if verbose and "before" in result:
                    parts.append(f"wallet={result['before']:.4f}→{result['after']:.4f}")
            parts.append("result=OK")
            logger.info(" ".join(parts))
            return result

        return wrapper

    return decorator
