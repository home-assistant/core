"""Decorator utility functions."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Any


class Registry[_KT: Hashable, _VT: Callable[..., Any]](dict[_KT, _VT]):
    """Registry of items."""

    def register(self, name: _KT) -> Callable[[_VT], _VT]:
        """Return decorator to register item with a specific name."""

        def decorator(func: _VT) -> _VT:
            """Register decorated function."""
            self[name] = func
            return func

        return decorator
