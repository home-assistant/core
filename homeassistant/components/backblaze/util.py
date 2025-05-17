"""Utilities for the Backblaze B2 integration."""

import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import Future
import io


class BufferedAsyncIteratorToSyncStream(io.RawIOBase):
    """An wrapper to make an AsyncIterator[bytes] a buffered synchronous readable stream."""

    _done: bool = False
    _read_future: Future[bytes] | None = None

    def __init__(self, iterator: AsyncIterator[bytes], buffer_size: int = 1024) -> None:
        """Initialize the stream."""
        self._buffer = bytearray()
        self._buffer_size = buffer_size
        self._iterator = iterator
        self._loop = asyncio.get_running_loop()

    def readable(self) -> bool:
        """Mark the stream as readable."""
        return True

    def _load_next_chunk(self) -> None:
        """Load the next chunk into the buffer."""
        if self._done:
            return

        if not self._read_future:
            # Fetch a larger chunk asynchronously
            self._read_future = asyncio.run_coroutine_threadsafe(
                self._fetch_next_chunk(), self._loop
            )

        if self._read_future.done():
            try:
                data = self._read_future.result()
                if data:
                    self._buffer.extend(data)
                else:
                    self._done = True
            except StopAsyncIteration:
                self._done = True
            except Exception as err:  # noqa: BLE001
                raise io.BlockingIOError(f"Failed to load chunk: {err}") from err
            finally:
                self._read_future = None

    async def _fetch_next_chunk(self) -> bytes:
        """Fetch multiple chunks until buffer size is filled."""
        chunks = []
        total_size = 0

        try:
            # Fill the buffer up to the specified size
            while total_size < self._buffer_size:
                chunk = await anext(self._iterator)
                chunks.append(chunk)
                total_size += len(chunk)
        except StopAsyncIteration:
            pass  # The end, return what we have

        return b"".join(chunks)

    def read(self, size: int = -1) -> bytes:
        """Read bytes."""
        if size == -1:
            # Read all remaining data
            while not self._done:
                self._load_next_chunk()
            size = len(self._buffer)

        # Ensure enough data in the buffer
        while len(self._buffer) < size and not self._done:
            self._load_next_chunk()

        # Return requested data
        data = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return bytes(data)

    def close(self) -> None:
        """Close the stream."""
        self._done = True
        super().close()
