"""Module for retry decorator."""

from functools import wraps


def retry(count=5, exc_type=Exception):
    """Retry function count times catching exc_type if it gets raised."""
    def decorator(func):
        """Decorator that accepts parameters."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            """Wrapped decorator."""
            for _ in range(count - 1):
                try:
                    return func(*args, **kwargs)
                except exc_type:  # pylint: disable=broad-except
                    pass
            return func(*args, **kwargs)
        return wrapper
    return decorator
