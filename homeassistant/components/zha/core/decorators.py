"""Decorators for ZHA core registries."""
from typing import Callable, TypeVar, Union

CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)  # pylint: disable=invalid-name


class DictRegistry(dict):
    """Dict Registry of items."""

    def register(
        self, name: Union[int, str], item: Union[str, CALLABLE_T] = None
    ) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Return decorator to register item with a specific name."""

        def decorator(channel: CALLABLE_T) -> CALLABLE_T:
            """Register decorated channel or item."""
            if item is None:
                self[name] = channel
            else:
                self[name] = item
            return channel

        return decorator


class SetRegistry(set):
    """Set Registry of items."""

    def register(self, name: Union[int, str]) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Return decorator to register item with a specific name."""

        def decorator(channel: CALLABLE_T) -> CALLABLE_T:
            """Register decorated channel or item."""
            self.add(name)
            return channel

        return decorator
