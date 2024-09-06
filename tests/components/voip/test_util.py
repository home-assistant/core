"""Test VoIP utils."""

import asyncio

import pytest

from homeassistant.components.voip.util import queue_to_iterable


async def test_queue_to_iterable() -> None:
    """Test queue_to_iterable."""
    queue: asyncio.Queue[int | None] = asyncio.Queue()
    expected_items = list(range(10))

    for i in expected_items:
        await queue.put(i)

    # Will terminate the stream
    await queue.put(None)

    actual_items = [item async for item in queue_to_iterable(queue)]

    assert expected_items == actual_items

    # Check timeout
    assert queue.empty()

    # Time out on first item
    async with asyncio.timeout(1):
        with pytest.raises(asyncio.TimeoutError):  # noqa: PT012
            # Should time out very quickly
            async for _item in queue_to_iterable(queue, timeout=0.01):
                await asyncio.sleep(1)

    # Check timeout on second item
    assert queue.empty()
    await queue.put(12345)

    # Time out on second item
    async with asyncio.timeout(1):
        with pytest.raises(asyncio.TimeoutError):  # noqa: PT012
            # Should time out very quickly
            async for item in queue_to_iterable(queue, timeout=0.01):
                if item != 12345:
                    await asyncio.sleep(1)

    assert queue.empty()
