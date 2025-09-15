"""Test the runner."""

import asyncio
from collections.abc import Iterator
import fcntl
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from unittest.mock import MagicMock, patch

import packaging.tags
import py
import pytest

from homeassistant import core, runner
from homeassistant.const import __version__
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
                raise Exception  # noqa: TRY002

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
        raise Exception("This is unhandled")  # noqa: TRY002

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


def test_ensure_single_execution_success(tmp_path: Path) -> None:
    """Test successful single instance execution."""
    config_dir = str(tmp_path)
    lock_file_path = tmp_path / runner.LOCK_FILE_NAME

    with runner.ensure_single_execution(config_dir) as lock:
        assert lock.exit_code is None
        assert lock_file_path.exists()

        with open(lock_file_path, encoding="utf-8") as f:
            data = json.load(f)
            assert data["pid"] == os.getpid()
            assert data["version"] == runner.LOCK_FILE_VERSION
            assert data["ha_version"] == __version__
            assert "start_ts" in data
            assert isinstance(data["start_ts"], float)

    # Lock file should still exist after context exit (we don't unlink to avoid races)
    assert lock_file_path.exists()


def test_ensure_single_execution_blocked(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """Test that second instance is blocked when lock exists."""
    config_dir = str(tmp_path)
    lock_file_path = tmp_path / runner.LOCK_FILE_NAME

    # Create and lock the file to simulate another instance
    with open(lock_file_path, "w+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        instance_info = {
            "pid": 12345,
            "version": 1,
            "ha_version": "2025.1.0",
            "start_ts": time.time() - 3600,  # Started 1 hour ago
        }
        json.dump(instance_info, lock_file)
        lock_file.flush()

        with runner.ensure_single_execution(config_dir) as lock:
            assert lock.exit_code == 1

        captured = capfd.readouterr()
        assert "Another Home Assistant instance is already running!" in captured.err
        assert "PID: 12345" in captured.err
        assert "Version: 2025.1.0" in captured.err
        assert "Started: " in captured.err
        # Should show local time since naive datetime
        assert "(local time)" in captured.err
        assert f"Config directory: {config_dir}" in captured.err


def test_ensure_single_execution_corrupt_lock_file(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """Test handling of corrupted lock file."""
    config_dir = str(tmp_path)
    lock_file_path = tmp_path / runner.LOCK_FILE_NAME

    with open(lock_file_path, "w+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write("not valid json{]")
        lock_file.flush()

        # Try to acquire lock (should set exit_code but handle corrupt file gracefully)
        with runner.ensure_single_execution(config_dir) as lock:
            assert lock.exit_code == 1

        # Check error output
        captured = capfd.readouterr()
        assert "Another Home Assistant instance is already running!" in captured.err
        assert "Unable to read lock file details:" in captured.err
        assert f"Config directory: {config_dir}" in captured.err


def test_ensure_single_execution_empty_lock_file(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """Test handling of empty lock file."""
    config_dir = str(tmp_path)
    lock_file_path = tmp_path / runner.LOCK_FILE_NAME

    with open(lock_file_path, "w+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Don't write anything - leave it empty
        lock_file.flush()

        # Try to acquire lock (should set exit_code but handle empty file gracefully)
        with runner.ensure_single_execution(config_dir) as lock:
            assert lock.exit_code == 1

        # Check error output
        captured = capfd.readouterr()
        assert "Another Home Assistant instance is already running!" in captured.err
        assert "Unable to read lock file details." in captured.err


def test_ensure_single_execution_with_timezone(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """Test handling of lock file with timezone info (edge case)."""
    config_dir = str(tmp_path)
    lock_file_path = tmp_path / runner.LOCK_FILE_NAME

    # Note: This tests an edge case - our code doesn't create timezone-aware timestamps,
    # but we handle them if they exist
    with open(lock_file_path, "w+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Started 2 hours ago
        instance_info = {
            "pid": 54321,
            "version": 1,
            "ha_version": "2025.2.0",
            "start_ts": time.time() - 7200,
        }
        json.dump(instance_info, lock_file)
        lock_file.flush()

        with runner.ensure_single_execution(config_dir) as lock:
            assert lock.exit_code == 1

        captured = capfd.readouterr()
        assert "Another Home Assistant instance is already running!" in captured.err
        assert "PID: 54321" in captured.err
        assert "Version: 2025.2.0" in captured.err
        assert "Started: " in captured.err
        # Should show local time indicator since fromtimestamp creates naive datetime
        assert "(local time)" in captured.err


def test_ensure_single_execution_with_tz_abbreviation(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """Test handling of lock file when timezone abbreviation is available."""
    config_dir = str(tmp_path)
    lock_file_path = tmp_path / runner.LOCK_FILE_NAME

    with open(lock_file_path, "w+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        instance_info = {
            "pid": 98765,
            "version": 1,
            "ha_version": "2025.3.0",
            "start_ts": time.time() - 1800,  # Started 30 minutes ago
        }
        json.dump(instance_info, lock_file)
        lock_file.flush()

        # Mock datetime to return a timezone abbreviation
        # We use mocking because strftime("%Z") behavior is OS-specific:
        # On some systems it returns empty string for naive datetimes
        mock_dt = MagicMock()

        def _mock_strftime(fmt: str) -> str:
            if fmt == "%Z":
                return "PST"
            if fmt == "%Y-%m-%d %H:%M:%S":
                return "2025-09-03 10:30:45"
            return "2025-09-03 10:30:45 PST"

        mock_dt.strftime.side_effect = _mock_strftime

        with patch("homeassistant.runner.datetime") as mock_datetime:
            mock_datetime.fromtimestamp.return_value = mock_dt
            with runner.ensure_single_execution(config_dir) as lock:
                assert lock.exit_code == 1

        captured = capfd.readouterr()
        assert "Another Home Assistant instance is already running!" in captured.err
        assert "PID: 98765" in captured.err
        assert "Version: 2025.3.0" in captured.err
        assert "Started: 2025-09-03 10:30:45 PST" in captured.err
        # Should NOT have "(local time)" when timezone abbreviation is present
        assert "(local time)" not in captured.err


def test_ensure_single_execution_file_not_unlinked(tmp_path: Path) -> None:
    """Test that lock file is never unlinked to avoid race conditions."""
    config_dir = str(tmp_path)
    lock_file_path = tmp_path / runner.LOCK_FILE_NAME

    # First run creates the lock file
    with runner.ensure_single_execution(config_dir) as lock:
        assert lock.exit_code is None
        assert lock_file_path.exists()
        # Get inode to verify it's the same file
        stat1 = lock_file_path.stat()

    # After context exit, file should still exist
    assert lock_file_path.exists()
    stat2 = lock_file_path.stat()
    # Verify it's the exact same file (same inode)
    assert stat1.st_ino == stat2.st_ino

    # Second run should reuse the same file
    with runner.ensure_single_execution(config_dir) as lock:
        assert lock.exit_code is None
        assert lock_file_path.exists()
        stat3 = lock_file_path.stat()
        # Still the same file (not recreated)
        assert stat1.st_ino == stat3.st_ino

    # After second run, still the same file
    assert lock_file_path.exists()
    stat4 = lock_file_path.stat()
    assert stat1.st_ino == stat4.st_ino


def test_ensure_single_execution_sequential_runs(tmp_path: Path) -> None:
    """Test that sequential runs work correctly after lock is released."""
    config_dir = str(tmp_path)
    lock_file_path = tmp_path / runner.LOCK_FILE_NAME

    with runner.ensure_single_execution(config_dir) as lock:
        assert lock.exit_code is None
        assert lock_file_path.exists()
        with open(lock_file_path, encoding="utf-8") as f:
            first_data = json.load(f)

    # Lock file should still exist after first run (not unlinked)
    assert lock_file_path.exists()

    # Small delay to ensure different timestamp
    time.sleep(0.00001)

    with runner.ensure_single_execution(config_dir) as lock:
        assert lock.exit_code is None
        assert lock_file_path.exists()
        with open(lock_file_path, encoding="utf-8") as f:
            second_data = json.load(f)
            assert second_data["pid"] == os.getpid()
            assert second_data["start_ts"] > first_data["start_ts"]

    # Lock file should still exist after second run (not unlinked)
    assert lock_file_path.exists()
