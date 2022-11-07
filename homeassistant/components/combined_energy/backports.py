"""Backport of async iterator methods added in Python 3.10."""
try:
    from builtins import aiter, anext  # type: ignore[attr-defined]
except ImportError:
    from collections.abc import AsyncIterable, AsyncIterator, Awaitable
    from typing import TypeVar

    _T = TypeVar("_T")

    def aiter(iterable: AsyncIterable[_T]) -> AsyncIterator[_T]:
        """Return an AsyncIterator for an AsyncIterable object."""
        return iterable.__aiter__()

    def anext(iterator: AsyncIterator[_T]) -> Awaitable[_T]:
        """Return the next item from the async iterator."""
        return iterator.__anext__()


__all__ = ("aiter", "anext")
