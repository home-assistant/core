"""Test Home Assistant executor util."""

import concurrent.futures
import time
from unittest.mock import patch

import pytest

from homeassistant.util import executor
from homeassistant.util.executor import InterruptibleThreadPoolExecutor


async def test_executor_shutdown_can_interrupt_threads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the executor shutdown can interrupt threads."""

    iexecutor = InterruptibleThreadPoolExecutor()

    def _loop_sleep_in_executor():
        while True:
            time.sleep(0.1)

    sleep_futures = [iexecutor.submit(_loop_sleep_in_executor) for _ in range(100)]

    iexecutor.shutdown()

    for future in sleep_futures:
        with pytest.raises((concurrent.futures.CancelledError, SystemExit)):
            future.result()

    assert "is still running at shutdown" in caplog.text
    assert "time.sleep(0.1)" in caplog.text


async def test_executor_shutdown_only_logs_max_attempts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the executor shutdown will only log max attempts."""

    iexecutor = InterruptibleThreadPoolExecutor()

    def _loop_sleep_in_executor():
        time.sleep(0.2)

    iexecutor.submit(_loop_sleep_in_executor)

    with patch.object(executor, "EXECUTOR_SHUTDOWN_TIMEOUT", 0.3):
        iexecutor.shutdown()

    assert "time.sleep(0.2)" in caplog.text
    assert "is still running at shutdown" in caplog.text
    iexecutor.shutdown()


async def test_executor_shutdown_does_not_log_shutdown_on_first_attempt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the executor shutdown does not log on first attempt."""

    iexecutor = InterruptibleThreadPoolExecutor()

    def _do_nothing():
        return

    for _ in range(5):
        iexecutor.submit(_do_nothing)

    iexecutor.shutdown()

    assert "is still running at shutdown" not in caplog.text


async def test_overall_timeout_reached(caplog: pytest.LogCaptureFixture) -> None:
    """Test that shutdown moves on when the overall timeout is reached."""

    def _loop_sleep_in_executor():
        time.sleep(1)

    with patch.object(executor, "EXECUTOR_SHUTDOWN_TIMEOUT", 0.5):
        iexecutor = InterruptibleThreadPoolExecutor()
        for _ in range(6):
            iexecutor.submit(_loop_sleep_in_executor)
        start = time.monotonic()
        iexecutor.shutdown()
        finish = time.monotonic()

    # Ideally execution time (finish - start) should be < 1.2 sec.
    # CI tests might not run in an ideal environment and timing might
    # not be accurate, so we let this test pass
    # if the duration is below 3 seconds.
    assert finish - start < 3.0

    iexecutor.shutdown()
