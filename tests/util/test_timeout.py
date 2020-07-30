"""Test Home Assistant timeout handler."""
import asyncio

import pytest

from homeassistant.util.timeout import ZoneTimeout


@pytest.fixture(autouse=True)
def fix_cool_down():
    """Patch cool down of the module."""
    from homeassistant.util import timeout

    timeout.COOL_DOWN = 0


async def test_simple_global_timeout():
    """Test a simple global timeout."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.asnyc_timeout(0.1):
            await asyncio.sleep(0.3)


async def test_simple_global_timeout_freeze():
    """Test a simple global timeout freeze."""
    timeout = ZoneTimeout()

    async with timeout.asnyc_timeout(0.2):
        async with timeout.freeze():
            await asyncio.sleep(0.3)


async def test_simple_global_timeout_freeze_reset():
    """Test a simple global timeout freeze reset."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.asnyc_timeout(0.2):
            async with timeout.freeze():
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.2)


async def test_simple_zone_timeout():
    """Test a simple zone timeout."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.asnyc_timeout(0.1, "test"):
            await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze():
    """Test a simple zone timeout freeze."""
    timeout = ZoneTimeout()

    async with timeout.asnyc_timeout(0.2, "test"):
        async with timeout.freeze("test"):
            await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze_reset():
    """Test a simple zone timeout freeze reset."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.asnyc_timeout(0.2, "test"):
            async with timeout.freeze("test"):
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.2, "test")


async def test_mix_zone_timeout_freeze():
    """Test a mix zone timeout global freeze."""
    timeout = ZoneTimeout()

    async with timeout.asnyc_timeout(0.2, "test"):
        async with timeout.freeze():
            await asyncio.sleep(0.3)


async def test_mix_zone_timeout():
    """Test a mix zone timeout global."""
    timeout = ZoneTimeout()

    async with timeout.asnyc_timeout(0.1):
        try:
            async with timeout.asnyc_timeout(0.2, "test"):
                await asyncio.sleep(0.4)
        except asyncio.TimeoutError:
            pass


async def test_mix_zone_timeout_trigger_global():
    """Test a mix zone timeout global with trigger it."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.asnyc_timeout(0.1):
            try:
                async with timeout.asnyc_timeout(0.1, "test"):
                    await asyncio.sleep(0.3)
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(0.3)
