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


class NestedDictRegistry(dict[int | str, dict[int | str | None, _TypeT]]):
    """Dict Registry of multiple items per key."""

    def register(
        self, name: int | str, sub_name: int | str | None = None
    ) -> Callable[[_TypeT], _TypeT]:
        """Return decorator to register item with a specific and a quirk name."""

        def decorator(cluster_handler: _TypeT) -> _TypeT:
            """Register decorated cluster handler or item."""
            if name not in self:
                self[name] = {}
            self[name][sub_name] = cluster_handler
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
