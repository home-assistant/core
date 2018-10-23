"""Decorator utility functions."""
from typing import Callable, TypeVar

CALLABLE_T = TypeVar('CALLABLE_T', bound=Callable)  # noqa pylint: disable=invalid-name


class Registry(dict):
    """Registry of items."""

    def register(self, name: str) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Return decorator to register item with a specific name."""
        def decorator(func: CALLABLE_T) -> CALLABLE_T:
            """Register decorated function."""
            self[name] = func
            return func

        return decorator
