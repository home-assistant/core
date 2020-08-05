"""Test Home Assistant timeout handler."""
import asyncio
import time

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
        async with timeout.async_timeout(0.1):
            await asyncio.sleep(0.3)


async def test_simple_global_timeout_with_executor_job(hass):
    """Test a simple global timeout with executor job."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.async_timeout(0.1):
            await hass.async_add_executor_job(lambda: time.sleep(0.2))


async def test_simple_global_timeout_freeze():
    """Test a simple global timeout freeze."""
    timeout = ZoneTimeout()

    async with timeout.async_timeout(0.2):
        async with timeout.freeze():
            await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze_inside_executor_job(hass):
    """Test a simple zone timeout freeze inside an executor job."""
    timeout = ZoneTimeout()

    def _some_sync_work():
        with timeout.freeze("recorder"):
            time.sleep(0.3)

    async with timeout.async_timeout(1.0):
        async with timeout.async_timeout(0.2, zone_name="recorder"):
            await hass.async_add_executor_job(_some_sync_work)


async def test_simple_global_timeout_freeze_inside_executor_job(hass):
    """Test a simple global timeout freeze inside an executor job."""
    timeout = ZoneTimeout()

    def _some_sync_work():
        with timeout.freeze():
            time.sleep(0.3)

    async with timeout.async_timeout(0.2):
        await hass.async_add_executor_job(_some_sync_work)


async def test_mix_global_timeout_freeze_and_zone_freeze_inside_executor_job(hass):
    """Test a simple global timeout freeze inside an executor job."""
    timeout = ZoneTimeout()

    def _some_sync_work():
        with timeout.freeze("recorder"):
            time.sleep(0.3)

    async with timeout.async_timeout(0.1):
        async with timeout.async_timeout(0.2, zone_name="recorder"):
            await hass.async_add_executor_job(_some_sync_work)


async def test_mix_global_timeout_freeze_and_zone_freeze_other_zone_inside_executor_job(
    hass,
):
    """Test a simple global timeout freeze other zone inside an executor job."""
    timeout = ZoneTimeout()

    def _some_sync_work():
        with timeout.freeze("not_recorder"):
            time.sleep(0.3)

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.async_timeout(0.1):
            async with timeout.async_timeout(0.2, zone_name="recorder"):
                async with timeout.async_timeout(0.2, zone_name="not_recorder"):
                    await hass.async_add_executor_job(_some_sync_work)


async def test_mix_global_timeout_freeze_and_zone_freeze_inside_executor_job_second_job_outside_zone_context(
    hass,
):
    """Test a simple global timeout freeze inside an executor job with second job outside of zone context."""
    timeout = ZoneTimeout()

    def _some_sync_work():
        with timeout.freeze("recorder"):
            time.sleep(0.3)

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.async_timeout(0.1):
            async with timeout.async_timeout(0.2, zone_name="recorder"):
                await hass.async_add_executor_job(_some_sync_work)
            await hass.async_add_executor_job(lambda: time.sleep(0.2))


async def test_simple_global_timeout_freeze_with_executor_job(hass):
    """Test a simple global timeout freeze with executor job."""
    timeout = ZoneTimeout()

    async with timeout.async_timeout(0.2):
        async with timeout.freeze():
            await hass.async_add_executor_job(lambda: time.sleep(0.3))


async def test_simple_global_timeout_freeze_reset():
    """Test a simple global timeout freeze reset."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.async_timeout(0.2):
            async with timeout.freeze():
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.2)


async def test_simple_zone_timeout():
    """Test a simple zone timeout."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.async_timeout(0.1, "test"):
            await asyncio.sleep(0.3)


async def test_multiple_zone_timeout():
    """Test a simple zone timeout."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.async_timeout(0.1, "test"):
            async with timeout.async_timeout(0.5, "test"):
                await asyncio.sleep(0.3)


async def test_different_zone_timeout():
    """Test a simple zone timeout."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.async_timeout(0.1, "test"):
            async with timeout.async_timeout(0.5, "other"):
                await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze():
    """Test a simple zone timeout freeze."""
    timeout = ZoneTimeout()

    async with timeout.async_timeout(0.2, "test"):
        async with timeout.freeze("test"):
            await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze_without_timeout():
    """Test a simple zone timeout freeze on a zone that does not have a timeout set."""
    timeout = ZoneTimeout()

    async with timeout.async_timeout(0.1, "test"):
        async with timeout.freeze("test"):
            await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze_reset():
    """Test a simple zone timeout freeze reset."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.async_timeout(0.2, "test"):
            async with timeout.freeze("test"):
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.2, "test")


async def test_mix_zone_timeout_freeze_and_global_freeze():
    """Test a mix zone timeout freeze and global freeze."""
    timeout = ZoneTimeout()

    async with timeout.async_timeout(0.2, "test"):
        async with timeout.freeze("test"):
            async with timeout.freeze():
                await asyncio.sleep(0.3)


async def test_mix_global_and_zone_timeout_freeze_():
    """Test a mix zone timeout freeze and global freeze."""
    timeout = ZoneTimeout()

    async with timeout.async_timeout(0.2, "test"):
        async with timeout.freeze():
            async with timeout.freeze("test"):
                await asyncio.sleep(0.3)


async def test_mix_zone_timeout_freeze():
    """Test a mix zone timeout global freeze."""
    timeout = ZoneTimeout()

    async with timeout.async_timeout(0.2, "test"):
        async with timeout.freeze():
            await asyncio.sleep(0.3)


async def test_mix_zone_timeout():
    """Test a mix zone timeout global."""
    timeout = ZoneTimeout()

    async with timeout.async_timeout(0.1):
        try:
            async with timeout.async_timeout(0.2, "test"):
                await asyncio.sleep(0.4)
        except asyncio.TimeoutError:
            pass


async def test_mix_zone_timeout_trigger_global():
    """Test a mix zone timeout global with trigger it."""
    timeout = ZoneTimeout()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout.async_timeout(0.1):
            try:
                async with timeout.async_timeout(0.1, "test"):
                    await asyncio.sleep(0.3)
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(0.3)


async def test_mix_zone_timeout_trigger_global_cool_down():
    """Test a mix zone timeout global with trigger it with cool_down."""
    timeout = ZoneTimeout()

    async with timeout.async_timeout(0.1, cool_down=0.3):
        try:
            async with timeout.async_timeout(0.1, "test"):
                await asyncio.sleep(0.3)
        except asyncio.TimeoutError:
            pass

        await asyncio.sleep(0.2)
