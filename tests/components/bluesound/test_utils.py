"""Tests for utils."""

import asyncio
from datetime import timedelta

from homeassistant.components.bluesound.utils import throttled


async def test_throttled_blocks_second_call() -> None:
    """Test that the throttled decorator blocks a second call within the delta time."""
    delta = timedelta(minutes=1)
    call_count = 0

    @throttled(delta)
    async def async_funx(value):
        nonlocal call_count
        call_count += 1

    await async_funx(1)
    await async_funx(2)

    assert call_count == 1


async def test_throttled_allows_second_call_after_delta() -> None:
    """Test that the throttled decorator allows a second call after the delta time."""
    delta = timedelta(microseconds=1)
    call_count = 0

    @throttled(delta)
    async def async_funx(value):
        nonlocal call_count
        call_count += 1

    await async_funx(1)
    await asyncio.sleep(0.001)
    await async_funx(2)

    assert call_count == 2
