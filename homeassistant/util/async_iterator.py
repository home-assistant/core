"""Async iterator utilities."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import CancelledError, Future
from typing import Self


class Abort(Exception):
    """Raised when abort is requested."""


class AsyncIteratorReader:
    """Allow reading from an AsyncIterator using blocking I/O.

    The class implements a blocking read method reading from the async iterator,
    and a close method.

    In addition, the abort method can be used to abort any ongoing read operation.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        stream: AsyncIterator[bytes],
    ) -> None:
        """Initialize the wrapper."""
        self._aborted = False
        self._exhausted = False
        self._loop = loop
        self._stream = stream
        self._buffer: bytes | None = None
        self._next_future: Future[bytes | None] | None = None
        self._pos: int = 0

    async def _next(self) -> bytes | None:
        """Get the next chunk from the iterator."""
        return await anext(self._stream, None)

    def abort(self) -> None:
        """Abort the reader."""
        self._aborted = True
        if self._next_future is not None:
            self._next_future.cancel()

    def read(self, n: int = -1, /) -> bytes:
        """Read up to n bytes of data from the iterator.

        The read method returns 0 bytes when the iterator is exhausted.
        """
        result = bytearray()
        while n < 0 or len(result) < n:
            if self._exhausted:
                break
            if not self._buffer:
                self._next_future = asyncio.run_coroutine_threadsafe(
                    self._next(), self._loop
                )
                if self._aborted:
                    self._next_future.cancel()
                    raise Abort
                try:
                    self._buffer = self._next_future.result()
                except CancelledError as err:
                    raise Abort from err
                self._pos = 0
            if not self._buffer:
                # The stream is exhausted
                self._exhausted = True
                break
            chunk = self._buffer[self._pos : self._pos + n]
            result.extend(chunk)
            n -= len(chunk)
            self._pos += len(chunk)
            if self._pos == len(self._buffer):
                self._buffer = None
        return bytes(result)

    def close(self) -> None:
        """Close the iterator."""


class AsyncIteratorWriter:
    """Allow writing to an AsyncIterator using blocking I/O.

    The class implements a blocking write method writing to the async iterator,
    as well as a close and tell methods.

    In addition, the abort method can be used to abort any ongoing write operation.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        """Initialize the wrapper."""
        self._aborted = False
        self._loop = loop
        self._pos: int = 0
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=1)
        self._write_future: Future[bytes | None] | None = None

    def __aiter__(self) -> Self:
        """Return the iterator."""
        return self

    async def __anext__(self) -> bytes:
        """Get the next chunk from the iterator."""
        if data := await self._queue.get():
            return data
        raise StopAsyncIteration

    def abort(self) -> None:
        """Abort the writer."""
        self._aborted = True
        if self._write_future is not None:
            self._write_future.cancel()

    def tell(self) -> int:
        """Return the current position in the iterator."""
        return self._pos

    def write(self, s: bytes, /) -> int:
        """Write data to the iterator.

        To signal the end of the stream, write a zero-length bytes object.
        """
        self._write_future = asyncio.run_coroutine_threadsafe(
            self._queue.put(s), self._loop
        )
        if self._aborted:
            self._write_future.cancel()
            raise Abort
        try:
            self._write_future.result()
        except CancelledError as err:
            raise Abort from err
        self._pos += len(s)
        return len(s)
