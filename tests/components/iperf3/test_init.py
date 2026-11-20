"""Tests for the iperf3 integration setup and test scheduling."""

import asyncio
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
    assert f"Unexpected error in the iperf3 test of {HOST_1}" in caplog.text
    assert "KeyError: 'end'" in caplog.text


async def test_cancelled_speedtest_holds_lock_until_test_ends(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test that cancelling a speedtest caller doesn't let another test start.

    Stopping a script that waits for iperf3.speedtest cancels the action, but
    its test keeps running in the executor thread.
    """
    lock = threading.Lock()
    running = 0
    max_running = 0
    started = threading.Event()
    second_started = threading.Event()
    release = threading.Event()

    def run() -> MagicMock:
        nonlocal running, max_running
        with lock:
            running += 1
            max_running = max(max_running, running)
            if mock_client.run.call_count > 1:
                second_started.set()
        started.set()
        release.wait(5)
        with lock:
            running -= 1
        return make_result()

    await setup_iperf3(hass, [HOST_1, HOST_2], manual=True)
    mock_client.run.side_effect = run

    def speedtest(host: str) -> asyncio.Task[None]:
        return hass.async_create_task(
            hass.services.async_call(DOMAIN, "speedtest", {"host": host}, blocking=True)
        )

    first = speedtest(HOST_1)
    try:
        assert await hass.async_add_executor_job(started.wait, 5)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

        # The first host's test still runs, so the second host has to wait.
        second = speedtest(HOST_2)
        assert not await hass.async_add_executor_job(second_started.wait, 0.2)
        assert mock_client.run.call_count == 1

        # Cancelling a waiting caller doesn't cancel the queued update.
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
    finally:
        release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert max_running == 1
    # Download and upload of both hosts.
    assert mock_client.run.call_count == 4


async def test_update_after_failing_to_schedule_test(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test that the lock is released when the test can't be scheduled."""
    await setup_iperf3(hass, [HOST_1, HOST_2], manual=True)

    with (
        patch.object(
            hass,
            "async_add_executor_job",
            side_effect=RuntimeError("cannot schedule new futures after shutdown"),
        ),
        pytest.raises(RuntimeError),
    ):
        await hass.services.async_call(
            DOMAIN, "speedtest", {"host": HOST_1}, blocking=True
        )

    async with asyncio.timeout(5):
        for host in (HOST_1, HOST_2):
            await hass.services.async_call(
                DOMAIN, "speedtest", {"host": host}, blocking=True
            )
    assert mock_client.run.call_count == 4


async def test_known_error_logged(
    hass: HomeAssistant, mock_client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a connection error is logged without a traceback."""
    await setup_iperf3(hass, [HOST_1], manual=True)
    mock_client.run.side_effect = OSError("Connection refused")

    await hass.services.async_call(DOMAIN, "speedtest", {"host": HOST_1}, blocking=True)
    await hass.async_block_till_done()

    assert "Iperf3 error: Connection refused" in caplog.text
    assert "Traceback" not in caplog.text
    assert hass.states.get("sensor.download_192_168_1_10").state == "unknown"


async def test_scheduled_update_skipped_while_previous_update_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the scan interval doesn't queue a host whose update still runs.

    A test can hang inside libiperf, so queuing another update on every interval
    would only pile them up.
    """
    started = threading.Event()
    release = threading.Event()

    def run() -> MagicMock:
        started.set()
        release.wait(5)
        return make_result()

    await setup_iperf3(hass, [HOST_1], manual=False)
    mock_client.run.side_effect = run

    freezer.tick(DEFAULT_INTERVAL)
    async_fire_time_changed(hass)
    try:
        assert await hass.async_add_executor_job(started.wait, 5)

        freezer.tick(DEFAULT_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            f"Skipping scheduled update of {HOST_1}, its previous update hasn't"
            in caplog.text
        )
        assert mock_client.run.call_count == 1
    finally:
        release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    # Download and upload of the first update only.
    assert mock_client.run.call_count == 2


async def test_speedtest_waits_for_update_underway(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test that a speedtest joins the host's update that is already running."""
    started = threading.Event()
    release = threading.Event()

    def run() -> MagicMock:
        started.set()
        release.wait(5)
        return make_result()

    await setup_iperf3(hass, [HOST_1], manual=True)
    mock_client.run.side_effect = run

    def speedtest() -> asyncio.Task[None]:
        return hass.async_create_task(
            hass.services.async_call(
                DOMAIN, "speedtest", {"host": HOST_1}, blocking=True
            )
        )

    first = speedtest()
    assert await hass.async_add_executor_job(started.wait, 5)
    second = speedtest()
    try:
        await asyncio.sleep(0)
        assert not second.done()
    finally:
        release.set()
    await asyncio.gather(first, second)

    # Both callers waited for the same update.
    assert mock_client.run.call_count == 2
    assert hass.states.get("sensor.download_192_168_1_10").state == "200.0"
