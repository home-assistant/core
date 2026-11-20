"""Tests for the iperf3 integration setup and test scheduling."""

import threading
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.iperf3 import Iperf3Data
from homeassistant.components.iperf3.const import DEFAULT_INTERVAL, DOMAIN
from homeassistant.core import HomeAssistant

from . import HOST_1, HOST_2, make_result, setup_iperf3


async def test_scheduled_tests_do_not_overlap(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_client: MagicMock
) -> None:
    """Test that the tests of several hosts run one after another.

    libiperf and the iperf3 wrapper are not thread safe, so tests running at the
    same time in different executor threads corrupt each other.
    """
    lock = threading.Lock()
    running = 0
    max_running = 0
    overlapped = threading.Event()

    def run() -> MagicMock:
        nonlocal running, max_running
        with lock:
            running += 1
            max_running = max(max_running, running)
            first = mock_client.run.call_count == 1
            if running > 1:
                overlapped.set()
        if first:
            # Give the other host's test the chance to start meanwhile.
            overlapped.wait(0.2)
        with lock:
            running -= 1
        return make_result()

    await setup_iperf3(hass, [HOST_1, HOST_2], manual=False)
    mock_client.run.side_effect = run

    freezer.tick(DEFAULT_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert max_running == 1
    # A download and an upload test for each host.
    assert mock_client.run.call_count == 4
    for host in (HOST_1, HOST_2):
        suffix = host.replace(".", "_")
        assert hass.states.get(f"sensor.download_{suffix}").state == "200.0"
        assert hass.states.get(f"sensor.upload_{suffix}").state == "100.0"


async def test_waiting_hosts_do_not_hold_executor_threads(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_client: MagicMock
) -> None:
    """Test that a host waiting for another host's test doesn't occupy a worker.

    A test can hang inside libiperf. The hosts queued behind it must wait in the
    event loop, not in executor threads, or enough of them exhaust the executor.
    """
    started = threading.Event()
    release = threading.Event()
    second_entered = threading.Event()
    entered: list[str] = []

    def run() -> MagicMock:
        started.set()
        release.wait(5)
        return make_result()

    update = Iperf3Data.update

    def spy_update(self: Iperf3Data, *args: object) -> None:
        entered.append(self.host)
        if len(entered) > 1:
            second_entered.set()
        update(self, *args)

    with patch.object(Iperf3Data, "update", spy_update):
        await setup_iperf3(hass, [HOST_1, HOST_2], manual=False)
        mock_client.run.side_effect = run

        freezer.tick(DEFAULT_INTERVAL)
        async_fire_time_changed(hass)
        try:
            assert await hass.async_add_executor_job(started.wait, 5)
            # Give the other host the chance to enter an executor thread.
            assert not await hass.async_add_executor_job(second_entered.wait, 0.2)
            assert len(entered) == 1
        finally:
            release.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert sorted(entered) == [HOST_1, HOST_2]


async def test_client_freed_before_next_test_after_unexpected_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a client is freed before the next test starts after an error.

    Deleting an iperf3 client calls into libiperf. A client kept alive by the
    traceback of an unexpected exception would be deleted later, while another
    host's test is already running.
    """
    alive = 0
    max_alive = 0

    class FakeClient:
        """iperf3 client whose result can't be parsed."""

        def __init__(self) -> None:
            nonlocal alive, max_alive
            alive += 1
            max_alive = max(max_alive, alive)

        def __del__(self) -> None:
            nonlocal alive
            alive -= 1

        def run(self) -> None:
            raise KeyError("end")

    with patch("homeassistant.components.iperf3.iperf3.Client", FakeClient):
        await setup_iperf3(hass, [HOST_1, HOST_2], manual=False)

        freezer.tick(DEFAULT_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert max_alive == 1
    assert alive == 0
    assert "Iperf3 error: 'end'" in caplog.text


async def test_update_skipped_while_previous_test_runs(
    hass: HomeAssistant, mock_client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a host isn't tested again while its previous test still runs.

    A test can hang inside libiperf, and starting a new one on every interval
    would pile up executor threads.
    """
    started = threading.Event()
    release = threading.Event()

    def run() -> MagicMock:
        started.set()
        release.wait(5)
        return make_result()

    await setup_iperf3(hass, [HOST_1], manual=True)
    mock_client.run.side_effect = run

    async def speedtest() -> None:
        await hass.services.async_call(
            DOMAIN, "speedtest", {"host": HOST_1}, blocking=True
        )

    first = hass.async_create_task(speedtest())
    try:
        assert await hass.async_add_executor_job(started.wait, 5)

        await speedtest()
        assert mock_client.run.call_count == 1
        assert f"previous iperf3 test of {HOST_1} is still running" in caplog.text
    finally:
        release.set()
    await first
    # Download and upload of the first update only.
    assert mock_client.run.call_count == 2
