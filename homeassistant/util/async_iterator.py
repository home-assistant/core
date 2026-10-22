"""Async iterator utilities."""

import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import CancelledError, Future
import logging
from typing import Any, Self

_LOGGER = logging.getLogger(__name__)


class Abort(Exception):
    """Raised when abort is requested."""


async def async_close_iterator(iterator: AsyncIterator[Any]) -> None:
    """Close an async iterator if it supports it.

    An iterator which is not fully consumed may hold resources, such as an HTTP
    connection, until it is closed. Errors are logged, not raised, so this can be
    used to clean up after another error.
    """
    if (aclose := getattr(iterator, "aclose", None)) is None:
        return
    try:
        await aclose()
    except Exception:
        _LOGGER.debug("Error closing %s", iterator, exc_info=True)


class AsyncIteratorReader:
    """Allow reading from an AsyncIterator using blocking I/O.

    The class implements a blocking read method reading from the async iterator,
    and a close method which closes the async iterator.

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
        # Held while reading, an async generator can't be closed during a read
        self._lock = asyncio.Lock()
        self._next_future: Future[bytes | None] | None = None
        self._pos: int = 0

    async def _next(self) -> bytes | None:
        """Get the next chunk from the iterator."""
        async with self._lock:
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
            if self._buffer is None:
                # The stream is exhausted
                self._exhausted = True
                break
            if n < 0:
                chunk = self._buffer[self._pos :]
            else:
                chunk = self._buffer[self._pos : self._pos + n]
                n -= len(chunk)
            result.extend(chunk)
            self._pos += len(chunk)
            if self._pos == len(self._buffer):
                self._buffer = None
        return bytes(result)

    def close(self) -> None:
        """Abort any ongoing read and close the iterator.

        The iterator is closed asynchronously on the event loop, this method may be
        called from any thread.
        """
        self.abort()
        asyncio.run_coroutine_threadsafe(self.aclose(), self._loop)

    async def aclose(self) -> None:
        """Abort any ongoing read and close the iterator."""
        self.abort()
        async with self._lock:
            await async_close_iterator(self._stream)


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

    async def aclose(self) -> None:
        """Abort the writer, which unblocks the thread writing to it."""
        self.abort()

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
