"""Async iterator utilities."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import CancelledError, Future
import contextlib
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


class ResourceChunkIterator:
    """Async iterator over chunks read from a resource, which closes the resource.

    A resource which is not fully read, for example an HTTP response, may hold a
    connection until it is closed. The resource is closed when it is fully read,
    when reading fails, when close() or aclose() is called, or when the iterator is
    garbage collected, whether or not iteration has started.

    read returns the next chunk, or empty bytes at the end of the resource. close
    closes the resource without waiting, aclose, if given, closes it gracefully and
    is used by aclose() and at the end of the resource. They are called from the
    event loop thread, also when the iterator is garbage collected in another
    thread, and must be safe to call while a read is in progress.

    close() and aclose() must be called from the event loop thread. Once the
    resource is closed, iteration stops. If reading failed, further reads raise the
    same error, so a truncated resource is not mistaken for a complete one.
    """

    __slots__ = (
        "_aclose",
        "_close",
        "_closed",
        "_error",
        "_exhausted",
        "_loop",
        "_read",
    )

    def __init__(
        self,
        read: Callable[[], Awaitable[bytes]],
        *,
        close: Callable[[], object],
        aclose: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Initialize."""
        self._read = read
        self._close = close
        self._aclose = aclose
        self._loop = asyncio.get_running_loop()
        self._closed = False
        self._error: BaseException | None = None
        self._exhausted = False

    def __aiter__(self) -> Self:
        """Return self."""
        return self

    async def __anext__(self) -> bytes:
        """Return the next chunk."""
        if self._error is not None:
            raise self._error
        if self._exhausted:
            raise StopAsyncIteration
        try:
            chunk = await self._read()
        except BaseException as err:
            if not self._exhausted:
                # Don't raise a cancellation in a task which was not cancelled
                self._error = (
                    err
                    if isinstance(err, Exception)
                    else RuntimeError("Reading the resource was interrupted")
                )
            self._close_resource()
            raise
        if not chunk:
            await self.aclose()
            raise StopAsyncIteration
        return chunk

    def _close_resource(self) -> None:
        """Close the resource without waiting, unless already closed."""
        if not self._closed:
            self._closed = True
            self._close()

    def close(self) -> None:
        """Close the resource without waiting, and stop iteration."""
        self._exhausted = True
        self._close_resource()

    async def aclose(self) -> None:
        """Close the resource, and stop iteration."""
        self._exhausted = True
        if self._aclose is None:
            self._close_resource()
            return
        if self._closed:
            return
        self._closed = True
        try:
            await self._aclose()
        except BaseException:
            # Don't leave the resource open if closing it gracefully failed
            self._close()
            raise

    def __del__(self) -> None:
        """Close the resource on the event loop when garbage collected."""
        if self._closed:
            return
        self._closed = True
        loop = self._loop
        if loop.is_closed():
            return
        try:
            running_loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is loop:
            self._close()
            return
        # The loop may be closed concurrently
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._close)
