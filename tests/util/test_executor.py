"""Test Home Assistant executor util."""

import concurrent.futures
import time

import pytest

from homeassistant.util.executor import InterruptibleThreadPoolExecutor


async def test_executor_shutdown_can_interrupt_threads(caplog):
    """Test that the executor shutdown can interrupt threads."""

    executor = InterruptibleThreadPoolExecutor()

    def _loop_sleep_in_executor():
        while True:
            time.sleep(0.1)

    sleep_futures = []

    for _ in range(100):
        sleep_futures.append(executor.submit(_loop_sleep_in_executor))

    executor.shutdown(cancel_futures=True, wait=True, interrupt=True)

    for future in sleep_futures:
        with pytest.raises((concurrent.futures.CancelledError, SystemExit)):
            future.result()

    assert "is still running at shutdown" in caplog.text
    assert "time.sleep(0.1)" in caplog.text


async def test_executor_shutdown_without_interrupt(caplog):
    """Test that the executor shutdown without interrupt."""

    executor = InterruptibleThreadPoolExecutor()

    def _loop_sleep_in_executor():
        time.sleep(0.1)
        return 50

    future = executor.submit(_loop_sleep_in_executor)

    executor.shutdown(cancel_futures=True, wait=True, interrupt=False)

    assert future.result() == 50

    assert "is still running at shutdown" not in caplog.text
    assert "time.sleep(0.1)" not in caplog.text
