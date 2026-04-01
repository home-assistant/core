"""Tests for async iterator utility functions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util.async_iterator import (
    Abort,
    AsyncIteratorReader,
    AsyncIteratorWriter,
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
