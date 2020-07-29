"""Test Home Assistant timeout handler."""
import asyncio

import pytest

from homeassistant.util.timeout import ZoneTimeout


async def test_simple_global_timeout():
    """Test a simple global timeout."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.asnyc_timeout(0.1):
            await asyncio.sleep(0.5)


async def test_simple_global_timeout_freeze():
    """Test a simple global timeout freeze."""
    timeout = ZoneTimeout()

    async with timeout.asnyc_timeout(0.2):
        async with timeout.freeze():
            await asyncio.sleep(0.3)


async def test_simple_zone_timeout():
    """Test a simple zone timeout."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.asnyc_timeout(0.1, "test"):
            await asyncio.sleep(0.5)


async def test_simple_zone_timeout_freeze():
    """Test a simple zone timeout freeze."""
    timeout = ZoneTimeout()

    async with timeout.asnyc_timeout(0.2, "test"):
        async with timeout.freeze("test"):
            await asyncio.sleep(0.3)


async def test_mix_zone_timeout_freeze():
    """Test a mix zone timeout global freeze."""
    timeout = ZoneTimeout()

    async with timeout.asnyc_timeout(0.2, "test"):
        async with timeout.freeze():
            await asyncio.sleep(0.3)
