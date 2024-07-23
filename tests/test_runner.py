"""Test the runner."""

import asyncio
from collections.abc import Iterator
import subprocess
import threading
from unittest.mock import patch

import packaging.tags
import py
import pytest

from homeassistant import core, runner
from homeassistant.core import HomeAssistant
from homeassistant.util import executor, thread

# https://github.com/home-assistant/supervisor/blob/main/supervisor/docker/homeassistant.py
SUPERVISOR_HARD_TIMEOUT = 240

TIMEOUT_SAFETY_MARGIN = 10


async def test_cumulative_shutdown_timeout_less_than_supervisor() -> None:
    """Verify the cumulative shutdown timeout is at least 10s less than the supervisor."""
    assert (
        core.STOPPING_STAGE_SHUTDOWN_TIMEOUT
        + core.STOP_STAGE_SHUTDOWN_TIMEOUT
        + core.FINAL_WRITE_STAGE_SHUTDOWN_TIMEOUT
        + core.CLOSE_STAGE_SHUTDOWN_TIMEOUT
        + executor.EXECUTOR_SHUTDOWN_TIMEOUT
        + thread.THREADING_SHUTDOWN_TIMEOUT
        + TIMEOUT_SAFETY_MARGIN
        <= SUPERVISOR_HARD_TIMEOUT
    )


async def test_setup_and_run_hass(hass: HomeAssistant, tmpdir: py.path.local) -> None:
    """Test we can setup and run."""
    test_dir = tmpdir.mkdir("config")
    default_config = runner.RuntimeConfig(test_dir)

    with (
        patch("homeassistant.bootstrap.async_setup_hass", return_value=hass),
        patch("threading._shutdown"),
        patch("homeassistant.core.HomeAssistant.async_run") as mock_run,
    ):
        await runner.setup_and_run_hass(default_config)
        assert threading._shutdown == thread.deadlock_safe_shutdown

    assert mock_run.called


def test_run(hass: HomeAssistant, tmpdir: py.path.local) -> None:
    """Test we can run."""
    test_dir = tmpdir.mkdir("config")
    default_config = runner.RuntimeConfig(test_dir)

    with (
        patch.object(runner, "TASK_CANCELATION_TIMEOUT", 1),
        patch("homeassistant.bootstrap.async_setup_hass", return_value=hass),
        patch("threading._shutdown"),
        patch("homeassistant.core.HomeAssistant.async_run") as mock_run,
    ):
        runner.run(default_config)

    assert mock_run.called


def test_run_executor_shutdown_throws(
    hass: HomeAssistant, tmpdir: py.path.local
) -> None:
    """Test we can run and we still shutdown if the executor shutdown throws."""
    test_dir = tmpdir.mkdir("config")
    default_config = runner.RuntimeConfig(test_dir)

    with (
        patch.object(runner, "TASK_CANCELATION_TIMEOUT", 1),
        pytest.raises(RuntimeError),
        patch("homeassistant.bootstrap.async_setup_hass", return_value=hass),
        patch("threading._shutdown"),
        patch(
            "homeassistant.runner.InterruptibleThreadPoolExecutor.shutdown",
            side_effect=RuntimeError,
        ) as mock_shutdown,
        patch(
            "homeassistant.core.HomeAssistant.async_run",
        ) as mock_run,
    ):
        runner.run(default_config)

    assert mock_shutdown.called
    assert mock_run.called


def test_run_does_not_block_forever_with_shielded_task(
    hass: HomeAssistant, tmpdir: py.path.local, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can shutdown and not block forever."""
    test_dir = tmpdir.mkdir("config")
    default_config = runner.RuntimeConfig(test_dir)
    tasks = []

    async def _async_create_tasks(*_):
        async def async_raise(*_):
            try:
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise Exception  # pylint: disable=broad-exception-raised

        async def async_shielded(*_):
            try:
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                await asyncio.sleep(2)

        tasks.append(asyncio.ensure_future(asyncio.shield(async_shielded())))
        tasks.append(asyncio.ensure_future(asyncio.sleep(2)))
        tasks.append(asyncio.ensure_future(async_raise()))
        await asyncio.sleep(0)
        return 0

    with (
        patch.object(runner, "TASK_CANCELATION_TIMEOUT", 0.1),
        patch("homeassistant.bootstrap.async_setup_hass", return_value=hass),
        patch("threading._shutdown"),
        patch("homeassistant.core.HomeAssistant.async_run", _async_create_tasks),
    ):
        runner.run(default_config)

    assert len(tasks) == 3
    assert (
        "Task could not be canceled and was still running after shutdown" in caplog.text
    )


async def test_unhandled_exception_traceback(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an unhandled exception gets a traceback in debug mode."""

    raised = asyncio.Event()

    async def _unhandled_exception():
        raised.set()
        # pylint: disable-next=broad-exception-raised
        raise Exception("This is unhandled")

    try:
        hass.loop.set_debug(True)
        task = asyncio.create_task(_unhandled_exception(), name="name_of_task")
        await raised.wait()
        # Delete it without checking result to trigger unhandled exception
        del task
    finally:
        hass.loop.set_debug(False)

    assert "Task exception was never retrieved" in caplog.text
    assert "This is unhandled" in caplog.text
    assert "_unhandled_exception" in caplog.text
    assert "name_of_task" in caplog.text


def test_enable_posix_spawn() -> None:
    """Test that we can enable posix_spawn on musllinux."""

    def _mock_sys_tags_any() -> Iterator[packaging.tags.Tag]:
        yield from packaging.tags.parse_tag("py3-none-any")

    def _mock_sys_tags_musl() -> Iterator[packaging.tags.Tag]:
        yield from packaging.tags.parse_tag("cp311-cp311-musllinux_1_1_x86_64")

    with (
        patch.object(subprocess, "_USE_POSIX_SPAWN", False),
        patch(
            "homeassistant.runner.packaging.tags.sys_tags",
            side_effect=_mock_sys_tags_musl,
        ),
    ):
        runner._enable_posix_spawn()
        assert subprocess._USE_POSIX_SPAWN is True

    with (
        patch.object(subprocess, "_USE_POSIX_SPAWN", False),
        patch(
            "homeassistant.runner.packaging.tags.sys_tags",
            side_effect=_mock_sys_tags_any,
        ),
    ):
        runner._enable_posix_spawn()
        assert subprocess._USE_POSIX_SPAWN is False
