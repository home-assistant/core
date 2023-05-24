"""Decorators for ZHA core registries."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

_TypeT = TypeVar("_TypeT", bound=type[Any])


class DictRegistry(dict[int | str, _TypeT]):
    """Dict Registry of items."""

    def register(self, name: int | str) -> Callable[[_TypeT], _TypeT]:
        """Return decorator to register item with a specific name."""

        def decorator(cluster_handler: _TypeT) -> _TypeT:
            """Register decorated cluster handler or item."""
            self[name] = cluster_handler
            return cluster_handler

        return decorator


class SetRegistry(set[int | str]):
    """Set Registry of items."""

    def register(self, name: int | str) -> Callable[[_TypeT], _TypeT]:
        """Return decorator to register item with a specific name."""

        def decorator(cluster_handler: _TypeT) -> _TypeT:
            """Register decorated cluster handler or item."""
            self.add(name)
            return cluster_handler

        return decorator
