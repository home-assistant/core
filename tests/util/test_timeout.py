"""Test Home Assistant timeout handler."""

import asyncio
from contextlib import suppress
import time

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util.timeout import TimeoutManager


async def test_simple_global_timeout() -> None:
    """Test a simple global timeout."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):
        async with timeout.async_timeout(0.1):
            await asyncio.sleep(0.3)


async def test_simple_global_timeout_with_executor_job(hass: HomeAssistant) -> None:
    """Test a simple global timeout with executor job."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):
        async with timeout.async_timeout(0.1):
            await hass.async_add_executor_job(time.sleep, 0.2)


async def test_simple_global_timeout_freeze() -> None:
    """Test a simple global timeout freeze."""
    timeout = TimeoutManager()

    async with timeout.async_timeout(0.2), timeout.async_freeze():
        await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze_inside_executor_job(
    hass: HomeAssistant,
) -> None:
    """Test a simple zone timeout freeze inside an executor job."""
    timeout = TimeoutManager()

    def _some_sync_work():
        with timeout.freeze("recorder"):
            time.sleep(0.3)

    async with (
        timeout.async_timeout(1.0),
        timeout.async_timeout(0.2, zone_name="recorder"),
    ):
        await hass.async_add_executor_job(_some_sync_work)


async def test_simple_global_timeout_freeze_inside_executor_job(
    hass: HomeAssistant,
) -> None:
    """Test a simple global timeout freeze inside an executor job."""
    timeout = TimeoutManager()

    def _some_sync_work():
        with timeout.freeze():
            time.sleep(0.3)

    async with timeout.async_timeout(0.2):
        await hass.async_add_executor_job(_some_sync_work)


async def test_mix_global_timeout_freeze_and_zone_freeze_inside_executor_job(
    hass: HomeAssistant,
) -> None:
    """Test a simple global timeout freeze inside an executor job."""
    timeout = TimeoutManager()

    def _some_sync_work():
        with timeout.freeze("recorder"):
            time.sleep(0.3)

    async with (
        timeout.async_timeout(0.1),
        timeout.async_timeout(0.2, zone_name="recorder"),
    ):
        await hass.async_add_executor_job(_some_sync_work)


async def test_mix_global_timeout_freeze_and_zone_freeze_different_order(
    hass: HomeAssistant,
) -> None:
    """Test a simple global timeout freeze inside an executor job before timeout was set."""
    timeout = TimeoutManager()

    def _some_sync_work():
        with timeout.freeze("recorder"):
            time.sleep(0.4)

    async with timeout.async_timeout(0.1):
        hass.async_add_executor_job(_some_sync_work)
        async with timeout.async_timeout(0.2, zone_name="recorder"):
            await asyncio.sleep(0.3)


async def test_mix_global_timeout_freeze_and_zone_freeze_other_zone_inside_executor_job(
    hass: HomeAssistant,
) -> None:
    """Test a simple global timeout freeze other zone inside an executor job."""
    timeout = TimeoutManager()

    def _some_sync_work():
        with timeout.freeze("not_recorder"):
            time.sleep(0.3)

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1):
            async with (
                timeout.async_timeout(0.2, zone_name="recorder"),
                timeout.async_timeout(0.2, zone_name="not_recorder"),
            ):
                await hass.async_add_executor_job(_some_sync_work)


async def test_mix_global_timeout_freeze_and_zone_freeze_inside_executor_job_second_job_outside_zone_context(
    hass: HomeAssistant,
) -> None:
    """Test a simple global timeout freeze inside an executor job with second job outside of zone context."""
    timeout = TimeoutManager()

    def _some_sync_work():
        with timeout.freeze("recorder"):
            time.sleep(0.3)

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1):
            async with timeout.async_timeout(0.2, zone_name="recorder"):
                await hass.async_add_executor_job(_some_sync_work)
            await hass.async_add_executor_job(time.sleep, 0.2)


async def test_simple_global_timeout_freeze_with_executor_job(
    hass: HomeAssistant,
) -> None:
    """Test a simple global timeout freeze with executor job."""
    timeout = TimeoutManager()

    async with timeout.async_timeout(0.2), timeout.async_freeze():
        await hass.async_add_executor_job(time.sleep, 0.3)


async def test_simple_global_timeout_does_not_leak_upward(
    hass: HomeAssistant,
) -> None:
    """Test a global timeout does not leak upward."""
    timeout = TimeoutManager()
    current_task = asyncio.current_task()
    assert current_task is not None
    cancelling_inside_timeout = None

    with pytest.raises(asyncio.TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1):
            cancelling_inside_timeout = current_task.cancelling()
            await asyncio.sleep(0.3)

    assert cancelling_inside_timeout == 0
    # After the context manager exits, the task should no longer be cancelling
    assert current_task.cancelling() == 0


async def test_simple_global_timeout_does_swallow_cancellation(
    hass: HomeAssistant,
) -> None:
    """Test a global timeout does not swallow cancellation."""
    timeout = TimeoutManager()
    current_task = asyncio.current_task()
    assert current_task is not None
    cancelling_inside_timeout = None

    async def task_with_timeout() -> None:
        nonlocal cancelling_inside_timeout
        new_task = asyncio.current_task()
        assert new_task is not None
        with pytest.raises(asyncio.TimeoutError):  # noqa: PT012
            cancelling_inside_timeout = new_task.cancelling()
            async with timeout.async_timeout(0.1):
                await asyncio.sleep(0.3)

    # After the context manager exits, the task should no longer be cancelling
    assert current_task.cancelling() == 0

    task = asyncio.create_task(task_with_timeout())
    await asyncio.sleep(0)
    task.cancel()
    assert task.cancelling() == 1

    assert cancelling_inside_timeout == 0
    # Cancellation should not leak into the current task
    assert current_task.cancelling() == 0
    # Cancellation should not be swallowed if the task is cancelled
    # and it also times out
    await asyncio.sleep(0)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelling() == 1


async def test_simple_global_timeout_freeze_reset() -> None:
    """Test a simple global timeout freeze reset."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.2):
            async with timeout.async_freeze():
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.2)


async def test_simple_zone_timeout() -> None:
    """Test a simple zone timeout."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):
        async with timeout.async_timeout(0.1, "test"):
            await asyncio.sleep(0.3)


async def test_simple_zone_timeout_does_not_leak_upward(
    hass: HomeAssistant,
) -> None:
    """Test a zone timeout does not leak upward."""
    timeout = TimeoutManager()
    current_task = asyncio.current_task()
    assert current_task is not None
    cancelling_inside_timeout = None

    with pytest.raises(asyncio.TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1, "test"):
            cancelling_inside_timeout = current_task.cancelling()
            await asyncio.sleep(0.3)

    assert cancelling_inside_timeout == 0
    # After the context manager exits, the task should no longer be cancelling
    assert current_task.cancelling() == 0


async def test_simple_zone_timeout_does_swallow_cancellation(
    hass: HomeAssistant,
) -> None:
    """Test a zone timeout does not swallow cancellation."""
    timeout = TimeoutManager()
    current_task = asyncio.current_task()
    assert current_task is not None
    cancelling_inside_timeout = None

    async def task_with_timeout() -> None:
        nonlocal cancelling_inside_timeout
        new_task = asyncio.current_task()
        assert new_task is not None
        with pytest.raises(asyncio.TimeoutError):  # noqa: PT012
            async with timeout.async_timeout(0.1, "test"):
                cancelling_inside_timeout = current_task.cancelling()
                await asyncio.sleep(0.3)

    # After the context manager exits, the task should no longer be cancelling
    assert current_task.cancelling() == 0

    task = asyncio.create_task(task_with_timeout())
    await asyncio.sleep(0)
    task.cancel()
    assert task.cancelling() == 1

    # Cancellation should not leak into the current task
    assert cancelling_inside_timeout == 0
    assert current_task.cancelling() == 0
    # Cancellation should not be swallowed if the task is cancelled
    # and it also times out
    await asyncio.sleep(0)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelling() == 1


async def test_multiple_zone_timeout() -> None:
    """Test a simple zone timeout."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1, "test"):
            async with timeout.async_timeout(0.5, "test"):
                await asyncio.sleep(0.3)


async def test_different_zone_timeout() -> None:
    """Test a simple zone timeout."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1, "test"):
            async with timeout.async_timeout(0.5, "other"):
                await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze() -> None:
    """Test a simple zone timeout freeze."""
    timeout = TimeoutManager()

    async with timeout.async_timeout(0.2, "test"), timeout.async_freeze("test"):
        await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze_without_timeout() -> None:
    """Test a simple zone timeout freeze on a zone that does not have a timeout set."""
    timeout = TimeoutManager()

    async with timeout.async_timeout(0.1, "test"), timeout.async_freeze("test"):
        await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze_reset() -> None:
    """Test a simple zone timeout freeze reset."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.2, "test"):
            async with timeout.async_freeze("test"):
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.2, "test")


async def test_mix_zone_timeout_freeze_and_global_freeze() -> None:
    """Test a mix zone timeout freeze and global freeze."""
    timeout = TimeoutManager()

    async with (
        timeout.async_timeout(0.2, "test"),
        timeout.async_freeze("test"),
        timeout.async_freeze(),
    ):
        await asyncio.sleep(0.3)


async def test_mix_global_and_zone_timeout_freeze_() -> None:
    """Test a mix zone timeout freeze and global freeze."""
    timeout = TimeoutManager()

    async with (
        timeout.async_timeout(0.2, "test"),
        timeout.async_freeze(),
        timeout.async_freeze("test"),
    ):
        await asyncio.sleep(0.3)


async def test_mix_zone_timeout_freeze() -> None:
    """Test a mix zone timeout global freeze."""
    timeout = TimeoutManager()

    async with timeout.async_timeout(0.2, "test"), timeout.async_freeze():
        await asyncio.sleep(0.3)


async def test_mix_zone_timeout() -> None:
    """Test a mix zone timeout global."""
    timeout = TimeoutManager()

    async with timeout.async_timeout(0.1):
        with suppress(TimeoutError):
            async with timeout.async_timeout(0.2, "test"):
                await asyncio.sleep(0.4)


async def test_mix_zone_timeout_trigger_global() -> None:
    """Test a mix zone timeout global with trigger it."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1):
            with suppress(TimeoutError):
                async with timeout.async_timeout(0.1, "test"):
                    await asyncio.sleep(0.3)

            await asyncio.sleep(0.3)


async def test_mix_zone_timeout_trigger_global_cool_down() -> None:
    """Test a mix zone timeout global with trigger it with cool_down."""
    timeout = TimeoutManager()

    async with timeout.async_timeout(0.1, cool_down=0.3):
        with suppress(TimeoutError):
            async with timeout.async_timeout(0.1, "test"):
                await asyncio.sleep(0.3)

        await asyncio.sleep(0.2)

    # Cleanup lingering (cool_down) task after test is done
    await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze_without_timeout_cleanup(
    hass: HomeAssistant,
) -> None:
    """Test a simple zone timeout freeze on a zone that does not have a timeout set."""
    timeout = TimeoutManager()

    async def background():
        async with timeout.async_freeze("test"):
            await asyncio.sleep(0.4)

    async with timeout.async_timeout(0.1):
        hass.async_create_task(background())
        await asyncio.sleep(0.2)


async def test_simple_zone_timeout_freeze_without_timeout_cleanup2(
    hass: HomeAssistant,
) -> None:
    """Test a simple zone timeout freeze on a zone that does not have a timeout set."""
    timeout = TimeoutManager()

    async def background():
        async with timeout.async_freeze("test"):
            await asyncio.sleep(0.2)

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1):
            hass.async_create_task(background())
            await asyncio.sleep(0.3)


async def test_simple_zone_timeout_freeze_without_timeout_exeption() -> None:
    """Test a simple zone timeout freeze on a zone that does not have a timeout set."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1):
            with suppress(RuntimeError):
                async with timeout.async_freeze("test"):
                    raise RuntimeError

            await asyncio.sleep(0.4)


async def test_simple_zone_timeout_zone_with_timeout_exception() -> None:
    """Test a simple zone timeout freeze on a zone that does not have a timeout set."""
    timeout = TimeoutManager()

    with pytest.raises(TimeoutError):  # noqa: PT012
        async with timeout.async_timeout(0.1):
            with suppress(RuntimeError):
                async with timeout.async_timeout(0.3, "test"):
                    raise RuntimeError

            await asyncio.sleep(0.3)


async def test_multiple_global_freezes(hass: HomeAssistant) -> None:
    """Test multiple global freezes."""
    timeout = TimeoutManager()

    async def background(delay: float) -> None:
        async with timeout.async_freeze():
            await asyncio.sleep(delay)

    async with timeout.async_timeout(0.1):
        task = hass.async_create_task(background(0.2))
        async with timeout.async_freeze():
            await asyncio.sleep(0.1)
    await task

    async with timeout.async_timeout(0.1):
        task = hass.async_create_task(background(0.2))
        async with timeout.async_freeze():
            await asyncio.sleep(0.3)
    await task
