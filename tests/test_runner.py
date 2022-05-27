"""Test the runner."""

import asyncio
import threading
from unittest.mock import patch

import pytest

from homeassistant import core, runner
from homeassistant.util import executor, thread

# https://github.com/home-assistant/supervisor/blob/main/supervisor/docker/homeassistant.py
SUPERVISOR_HARD_TIMEOUT = 220

TIMEOUT_SAFETY_MARGIN = 10


async def test_cumulative_shutdown_timeout_less_than_supervisor():
    """Verify the cumulative shutdown timeout is at least 10s less than the supervisor."""
    assert (
        core.STAGE_1_SHUTDOWN_TIMEOUT
        + core.STAGE_2_SHUTDOWN_TIMEOUT
        + core.STAGE_3_SHUTDOWN_TIMEOUT
        + executor.EXECUTOR_SHUTDOWN_TIMEOUT
        + thread.THREADING_SHUTDOWN_TIMEOUT
        + TIMEOUT_SAFETY_MARGIN
        <= SUPERVISOR_HARD_TIMEOUT
    )


async def test_setup_and_run_hass(hass, tmpdir):
    """Test we can setup and run."""
    test_dir = tmpdir.mkdir("config")
    default_config = runner.RuntimeConfig(test_dir)

    with patch("homeassistant.bootstrap.async_setup_hass", return_value=hass), patch(
        "threading._shutdown"
    ), patch("homeassistant.core.HomeAssistant.async_run") as mock_run:
        await runner.setup_and_run_hass(default_config)
        assert threading._shutdown == thread.deadlock_safe_shutdown

    assert mock_run.called


def test_run(hass, tmpdir):
    """Test we can run."""
    test_dir = tmpdir.mkdir("config")
    default_config = runner.RuntimeConfig(test_dir)

    with patch.object(runner, "TASK_CANCELATION_TIMEOUT", 1), patch(
        "homeassistant.bootstrap.async_setup_hass", return_value=hass
    ), patch("threading._shutdown"), patch(
        "homeassistant.core.HomeAssistant.async_run"
    ) as mock_run:
        runner.run(default_config)

    assert mock_run.called


def test_run_executor_shutdown_throws(hass, tmpdir):
    """Test we can run and we still shutdown if the executor shutdown throws."""
    test_dir = tmpdir.mkdir("config")
    default_config = runner.RuntimeConfig(test_dir)

    with patch.object(runner, "TASK_CANCELATION_TIMEOUT", 1), pytest.raises(
        RuntimeError
    ), patch("homeassistant.bootstrap.async_setup_hass", return_value=hass), patch(
        "threading._shutdown"
    ), patch(
        "homeassistant.runner.InterruptibleThreadPoolExecutor.shutdown",
        side_effect=RuntimeError,
    ) as mock_shutdown, patch(
        "homeassistant.core.HomeAssistant.async_run"
    ) as mock_run:
        runner.run(default_config)

    assert mock_shutdown.called
    assert mock_run.called


def test_run_does_not_block_forever_with_shielded_task(hass, tmpdir, caplog):
    """Test we can shutdown and not block forever."""
    test_dir = tmpdir.mkdir("config")
    default_config = runner.RuntimeConfig(test_dir)
    created_tasks = False

    async def _async_create_tasks(*_):
        nonlocal created_tasks

        async def async_raise(*_):
            try:
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise Exception

        async def async_shielded(*_):
            try:
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                await asyncio.sleep(2)

        asyncio.ensure_future(asyncio.shield(async_shielded()))
        asyncio.ensure_future(asyncio.sleep(2))
        asyncio.ensure_future(async_raise())
        await asyncio.sleep(0.1)
        created_tasks = True
        return 0

    with patch.object(runner, "TASK_CANCELATION_TIMEOUT", 1), patch(
        "homeassistant.bootstrap.async_setup_hass", return_value=hass
    ), patch("threading._shutdown"), patch(
        "homeassistant.core.HomeAssistant.async_run", _async_create_tasks
    ):
        runner.run(default_config)

    assert created_tasks is True
    assert (
        "Task could not be canceled and was still running after shutdown" in caplog.text
    )


async def test_unhandled_exception_traceback(hass, caplog):
    """Test an unhandled exception gets a traceback in debug mode."""

    async def _unhandled_exception():
        raise Exception("This is unhandled")

    try:
        hass.loop.set_debug(True)
        asyncio.create_task(_unhandled_exception())
    finally:
        hass.loop.set_debug(False)

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert "Task exception was never retrieved" in caplog.text
    assert "This is unhandled" in caplog.text
    assert "_unhandled_exception" in caplog.text
