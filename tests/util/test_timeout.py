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


async def test_simple_zone_timeout():
    """Test a simple zone timeout."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.asnyc_timeout(0.1, "test"):
            await asyncio.sleep(0.5)
