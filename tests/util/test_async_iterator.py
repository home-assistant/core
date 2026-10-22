"""Tests for async iterator utility functions."""

import asyncio
from collections.abc import AsyncIterator
import logging

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util.async_iterator import (
    Abort,
    AsyncIteratorReader,
    AsyncIteratorWriter,
    async_close_iterator,
)


def _read_all(reader: AsyncIteratorReader) -> bytes:
    output = b""
    while chunk := reader.read(500):
        output += chunk
    return output


async def test_async_iterator_reader(hass: HomeAssistant) -> None:
    """Test the async iterator reader."""
    data = b"hello world" * 1000

    async def async_gen() -> AsyncIterator[bytes]:
        for _ in range(10):
            yield data

    reader = AsyncIteratorReader(hass.loop, async_gen())
    assert await hass.async_add_executor_job(_read_all, reader) == data * 10


@pytest.mark.parametrize(
    "read_args",
    [
        pytest.param((), id="no_argument"),
        pytest.param((-1,), id="negative_one"),
    ],
)
async def test_async_iterator_reader_read_all(
    hass: HomeAssistant, read_args: tuple[int, ...]
) -> None:
    """Test read() without a size returns the rest of the stream."""

    async def async_gen() -> AsyncIterator[bytes]:
        yield b"a"
        yield b"hello"
        yield b"world"

    reader = AsyncIteratorReader(hass.loop, async_gen())

    def _read_partial_then_rest() -> tuple[bytes, bytes, bytes]:
        return reader.read(3), reader.read(*read_args), reader.read(*read_args)

    assert await hass.async_add_executor_job(_read_partial_then_rest) == (
        b"ahe",
        b"lloworld",
        b"",
    )


async def test_async_iterator_reader_empty_chunk(hass: HomeAssistant) -> None:
    """Test an empty chunk is not treated as the end of the stream."""

    async def async_gen() -> AsyncIterator[bytes]:
        yield b"hello"
        yield b""
        yield b"world"

    reader = AsyncIteratorReader(hass.loop, async_gen())
    assert await hass.async_add_executor_job(_read_all, reader) == b"helloworld"


async def test_async_iterator_reader_abort_early(hass: HomeAssistant) -> None:
    """Test abort the async iterator reader."""
    evt = asyncio.Event()

    async def async_gen() -> AsyncIterator[bytes]:
        await evt.wait()
        yield b""

    reader = AsyncIteratorReader(hass.loop, async_gen())
    reader.abort()
    fut = hass.async_add_executor_job(_read_all, reader)
    with pytest.raises(Abort):
        await fut


async def test_async_iterator_reader_abort_late(hass: HomeAssistant) -> None:
    """Test abort the async iterator reader."""
    evt = asyncio.Event()

    async def async_gen() -> AsyncIterator[bytes]:
        await evt.wait()
        yield b""

    reader = AsyncIteratorReader(hass.loop, async_gen())
    fut = hass.async_add_executor_job(_read_all, reader)
    await asyncio.sleep(0.1)
    reader.abort()
    with pytest.raises(Abort):
        await fut


def _write_all(writer: AsyncIteratorWriter, data: list[bytes]) -> bytes:
    for chunk in data:
        assert writer.write(chunk) == len(chunk)
    assert writer.write(b"") == 0


async def test_async_iterator_writer(hass: HomeAssistant) -> None:
    """Test the async iterator writer."""
    chunk = b"hello world" * 1000
    chunks = [chunk] * 10
    writer = AsyncIteratorWriter(hass.loop)

    fut = hass.async_add_executor_job(_write_all, writer, chunks)

    read = b""
    async for data in writer:
        read += data

    await fut

    assert read == chunk * 10
    assert writer.tell() == len(read)


async def test_async_iterator_writer_abort_early(hass: HomeAssistant) -> None:
    """Test the async iterator writer."""
    chunk = b"hello world" * 1000
    chunks = [chunk] * 10
    writer = AsyncIteratorWriter(hass.loop)
    writer.abort()

    fut = hass.async_add_executor_job(_write_all, writer, chunks)

    with pytest.raises(Abort):
        await fut


async def test_async_iterator_writer_abort_late(hass: HomeAssistant) -> None:
    """Test the async iterator writer."""
    chunk = b"hello world" * 1000
    chunks = [chunk] * 10
    writer = AsyncIteratorWriter(hass.loop)

    fut = hass.async_add_executor_job(_write_all, writer, chunks)
    await asyncio.sleep(0.1)
    writer.abort()

    with pytest.raises(Abort):
        await fut


async def test_async_iterator_reader_exhausted(hass: HomeAssistant) -> None:
    """Test that read() returns empty bytes after stream exhaustion."""

    async def async_gen() -> AsyncIterator[bytes]:
        yield b"hello"

    reader = AsyncIteratorReader(hass.loop, async_gen())

    def _read_then_read_again() -> bytes:
        data = _read_all(reader)
        # Second read after exhaustion should return b"" immediately
        assert reader.read(500) == b""
        return data

    assert await hass.async_add_executor_job(_read_then_read_again) == b"hello"


async def test_async_iterator_reader_aclose(hass: HomeAssistant) -> None:
    """Test aclose closes a partially read stream."""
    closed = asyncio.Event()

    async def async_gen() -> AsyncIterator[bytes]:
        try:
            yield b"hello"
            yield b"world"
        finally:
            closed.set()

    reader = AsyncIteratorReader(hass.loop, async_gen())
    assert await hass.async_add_executor_job(reader.read, 5) == b"hello"
    assert not closed.is_set()

    await reader.aclose()
    assert closed.is_set()


async def test_async_iterator_reader_close_from_thread(hass: HomeAssistant) -> None:
    """Test close called from a thread closes a partially read stream."""
    closed = asyncio.Event()

    async def async_gen() -> AsyncIterator[bytes]:
        try:
            yield b"hello"
            yield b"world"
        finally:
            closed.set()

    reader = AsyncIteratorReader(hass.loop, async_gen())

    def _read_then_close() -> bytes:
        data = reader.read(5)
        reader.close()
        return data

    assert await hass.async_add_executor_job(_read_then_close) == b"hello"
    async with asyncio.timeout(1):
        await closed.wait()


async def test_async_iterator_reader_aclose_during_read(hass: HomeAssistant) -> None:
    """Test aclose aborts an ongoing read before closing the stream."""
    reading = asyncio.Event()
    closed = asyncio.Event()

    async def async_gen() -> AsyncIterator[bytes]:
        try:
            reading.set()
            await asyncio.Event().wait()
            yield b"never"
        finally:
            closed.set()

    reader = AsyncIteratorReader(hass.loop, async_gen())
    fut = hass.async_add_executor_job(_read_all, reader)
    await reading.wait()

    await reader.aclose()
    assert closed.is_set()
    with pytest.raises(Abort):
        await fut


async def test_async_iterator_reader_aclose_not_supported(
    hass: HomeAssistant,
) -> None:
    """Test aclose of a stream which can't be closed."""

    class Stream:
        def __aiter__(self) -> Stream:
            return self

        async def __anext__(self) -> bytes:
            return b"hello"

    reader = AsyncIteratorReader(hass.loop, Stream())
    assert await hass.async_add_executor_job(reader.read, 5) == b"hello"
    await reader.aclose()


async def test_async_close_iterator_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test errors when closing an iterator are logged, not raised."""

    async def async_gen() -> AsyncIterator[bytes]:
        try:
            yield b"hello"
        finally:
            raise OSError("Boom!")

    stream = async_gen()
    assert await anext(stream) == b"hello"

    with caplog.at_level(logging.DEBUG):
        await async_close_iterator(stream)
    assert "Error closing" in caplog.text
    assert "Boom!" in caplog.text


async def test_async_iterator_writer_aclose(hass: HomeAssistant) -> None:
    """Test aclose unblocks a thread writing to the writer."""
    writer = AsyncIteratorWriter(hass.loop)

    fut = hass.async_add_executor_job(_write_all, writer, [b"hello", b"world"])
    assert await anext(writer) == b"hello"
    await writer.aclose()

    with pytest.raises(Abort):
        await fut
