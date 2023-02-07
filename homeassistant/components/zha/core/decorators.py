"""Decorators for ZHA core registries."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

_TypeT = TypeVar("_TypeT", bound=type[Any])


class DictRegistry(dict[int | str, _TypeT]):
    """Dict Registry of items."""

    def register(self, name: int | str) -> Callable[[_TypeT], _TypeT]:
        """Return decorator to register item with a specific name."""

        def decorator(channel: _TypeT) -> _TypeT:
            """Register decorated channel or item."""
            self[name] = channel
            return channel

        return decorator


class SetRegistry(set[int | str]):
    """Set Registry of items."""

    def register(self, name: int | str) -> Callable[[_TypeT], _TypeT]:
        """Return decorator to register item with a specific name."""

        def decorator(channel: _TypeT) -> _TypeT:
            """Register decorated channel or item."""
            self.add(name)
            return channel

        return decorator
