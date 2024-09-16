"""Voip util functions."""

from __future__ import annotations

from asyncio import Queue, timeout as async_timeout
from collections.abc import AsyncIterable
from typing import Any

from typing_extensions import TypeVar

_DataT = TypeVar("_DataT", default=Any)


async def queue_to_iterable(
    queue: Queue[_DataT], timeout: float | None = None
) -> AsyncIterable[_DataT]:
    """Stream items from a queue until None with an optional timeout per item."""
    if timeout is None:
        while (item := await queue.get()) is not None:
            yield item
    else:
        async with async_timeout(timeout):
            item = await queue.get()

        while item is not None:
            yield item
            async with async_timeout(timeout):
                item = await queue.get()
