"""Backport of async iterator methods added in Python 3.10."""
try:
    from builtins import anext  # type: ignore[attr-defined]
except ImportError:
    from collections.abc import AsyncIterator, Awaitable
    from typing import TypeVar

    _T = TypeVar("_T")

    def anext(iterator: AsyncIterator[_T]) -> Awaitable[_T]:
        """Return the next item from the async iterator."""
        return iterator.__anext__()


__all__ = ("anext",)
