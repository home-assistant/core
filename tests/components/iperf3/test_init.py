"""Tests for the iperf3 integration setup and test scheduling."""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.iperf3 import Iperf3Data
from homeassistant.components.iperf3.const import DEFAULT_INTERVAL, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback

from . import HOST_1, HOST_2, make_result, setup_iperf3

DOWNLOAD_ENTITY_ID_1 = "sensor.download_192_168_1_10"


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


class BlockingRun:
    """Side effect for the client's run() that blocks until released."""

    def __init__(self) -> None:
        """Initialize the side effect."""
        self._lock = threading.Lock()
        self._running = 0
        self.max_running = 0
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(self) -> MagicMock:
        """Count the running tests and block until released."""
        with self._lock:
            self._running += 1
            self.max_running = max(self.max_running, self._running)
        self.started.set()
        self.release.wait(5)
        with self._lock:
            self._running -= 1
        return make_result()


def _speedtest(hass: HomeAssistant, host: str) -> asyncio.Task[None]:
    """Call the speedtest action for a host in a task."""
    return hass.async_create_task(
        hass.services.async_call(DOMAIN, "speedtest", {"host": host}, blocking=True)
    )


async def test_cancelled_speedtest_holds_lock_until_test_ends(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test that cancelling a speedtest caller doesn't let another test start.

    Stopping a script that waits for the action cancels it, but its test keeps
    running in the executor thread, inside libiperf.
    """
    run = mock_client.run.side_effect = BlockingRun()
    await setup_iperf3(hass, [HOST_1, HOST_2], manual=True)

    first = _speedtest(hass, HOST_1)
    assert await hass.async_add_executor_job(run.started.wait, 5)
    try:
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

        # The first host's test still runs, so the second host has to wait.
        second = _speedtest(hass, HOST_2)
        await hass.async_add_executor_job(time.sleep, 0.2)
        assert mock_client.run.call_count == 1

        # Cancelling a waiting caller doesn't cancel the queued update.
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
    finally:
        run.release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert run.max_running == 1
    # Download and upload of both hosts.
    assert mock_client.run.call_count == 4


async def test_shutdown_holds_lock_until_test_ends(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test that stopping Home Assistant doesn't let another test start.

    Shutdown cancels the running update, but its test keeps running inside
    libiperf, and an automation on the stop event can still start an update.
    """
    run = mock_client.run.side_effect = BlockingRun()
    await setup_iperf3(hass, [HOST_1, HOST_2], manual=True)
    stopping = asyncio.Event()

    @callback
    def update_on_stop(event: Event) -> None:
        _speedtest(hass, HOST_2)
        stopping.set()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, update_on_stop)

    first = _speedtest(hass, HOST_1)
    assert await hass.async_add_executor_job(run.started.wait, 5)
    stop = asyncio.create_task(hass.async_stop())
    try:
        async with asyncio.timeout(5):
            await stopping.wait()
        await hass.async_add_executor_job(time.sleep, 0.2)
        assert mock_client.run.call_count == 1
    finally:
        run.release.set()
    await stop

    with pytest.raises(asyncio.CancelledError):
        await first
    assert run.max_running == 1
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
    assert hass.states.get(DOWNLOAD_ENTITY_ID_1).state == "unknown"


async def test_scheduled_update_skipped_while_previous_update_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the scan interval doesn't queue a host whose update still runs.

    A test can hang inside libiperf, so queuing another update on every interval
    would only pile them up. The skip is logged once per unfinished update.
    """
    started = threading.Event()
    release = threading.Event()
    warning = f"Skipping scheduled updates of {HOST_1} until its previous update"

    def run() -> MagicMock:
        started.set()
        release.wait(5)
        return make_result()

    await setup_iperf3(hass, [HOST_1], manual=False)
    mock_client.run.side_effect = run

    async def stall_and_skip() -> None:
        """Start an update that blocks, then fire two more intervals."""
        freezer.tick(DEFAULT_INTERVAL)
        async_fire_time_changed(hass)
        try:
            assert await hass.async_add_executor_job(started.wait, 5)
            for _ in range(2):
                freezer.tick(DEFAULT_INTERVAL)
                async_fire_time_changed(hass)
                await hass.async_block_till_done()
        finally:
            release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        started.clear()
        release.clear()

    await stall_and_skip()
    assert caplog.text.count(warning) == 1
    # Download and upload of the first update only.
    assert mock_client.run.call_count == 2

    # A later stall is reported again.
    await stall_and_skip()
    assert caplog.text.count(warning) == 2
    assert mock_client.run.call_count == 4


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
    # The sensors refresh in their own executor jobs after the update.
    await hass.async_block_till_done()

    # Both callers waited for the same update.
    assert mock_client.run.call_count == 2
    assert hass.states.get(DOWNLOAD_ENTITY_ID_1).state == "200.0"
