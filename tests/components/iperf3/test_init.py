"""Tests for the iperf3 integration setup and test scheduling."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
import time
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.iperf3 import Iperf3Data
from homeassistant.components.iperf3.const import DEFAULT_INTERVAL, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback

from . import HOST_1, HOST_2, BlockingRun, setup_iperf3

DOWNLOAD_ENTITY_ID_1 = "sensor.download_192_168_1_10"
DOWNLOAD_ENTITY_ID_2 = "sensor.download_192_168_1_11"
UPLOAD_ENTITY_ID_1 = "sensor.upload_192_168_1_10"
UPLOAD_ENTITY_ID_2 = "sensor.upload_192_168_1_11"


def _speedtest(hass: HomeAssistant, host: str) -> asyncio.Task[None]:
    """Call the speedtest action for a host in a task."""
    return hass.async_create_task(
        hass.services.async_call(DOMAIN, "speedtest", {"host": host}, blocking=True)
    )


async def test_scheduled_tests_do_not_overlap(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_client: MagicMock
) -> None:
    """Test that the tests of several hosts run one after another.

    libiperf and the iperf3 wrapper are not thread safe, so tests running at the
    same time in different executor threads corrupt each other.
    """
    # Each test runs long enough for another host's test to start meanwhile.
    run = mock_client.run.side_effect = BlockingRun(hold=0.1)
    await setup_iperf3(hass, [HOST_1, HOST_2], manual=False)

    freezer.tick(DEFAULT_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert run.max_running == 1
    # A download and an upload test for each host.
    assert mock_client.run.call_count == 4
    assert hass.states.get(DOWNLOAD_ENTITY_ID_1).state == "200.0"
    assert hass.states.get(UPLOAD_ENTITY_ID_1).state == "100.0"
    assert hass.states.get(DOWNLOAD_ENTITY_ID_2).state == "200.0"
    assert hass.states.get(UPLOAD_ENTITY_ID_2).state == "100.0"


async def test_waiting_hosts_do_not_hold_executor_threads(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, blocking_run: BlockingRun
) -> None:
    """Test that a host waiting for another host's test doesn't occupy a worker.

    A test can hang inside libiperf. The hosts queued behind it must wait in the
    event loop, not in executor threads, or enough of them exhaust the executor.
    """
    await setup_iperf3(hass, [HOST_1, HOST_2], manual=False)

    with patch.object(
        hass, "async_add_executor_job", wraps=hass.async_add_executor_job
    ) as add_executor_job:
        freezer.tick(DEFAULT_INTERVAL)
        async_fire_time_changed(hass)
        await blocking_run.async_wait_started(hass)
        # Give the other host the chance to enter an executor thread.
        await hass.async_add_executor_job(time.sleep, 0.2)
        assert _iperf3_jobs(add_executor_job) == [HOST_1]

        blocking_run.release.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert sorted(_iperf3_jobs(add_executor_job)) == [HOST_1, HOST_2]


def _iperf3_jobs(add_executor_job: MagicMock) -> list[str]:
    """Return the hosts whose iperf3 jobs were submitted to the executor."""
    return [
        call.args[0].__self__.host
        for call in add_executor_job.call_args_list
        if isinstance(getattr(call.args[0], "__self__", None), Iperf3Data)
    ]


def _fail_known(client: object) -> None:
    """Fail the test with an error the integration expects."""
    raise OSError("Connection refused")


def _fail_unexpected(client: object) -> None:
    """Fail the test with an error the integration doesn't expect."""
    raise KeyError("end")


def _parse_result(client: object) -> None:
    """Fail to parse the result while holding the client in this frame."""
    raise ValueError("Extra data")


def _fail_chained(client: object) -> None:
    """Fail the test with an unexpected error chained to another one."""
    try:
        _parse_result(client)
    except ValueError as err:
        raise KeyError("end") from err


@pytest.mark.parametrize(
    ("fail", "expectation", "logged"),
    [
        pytest.param(
            _fail_known,
            nullcontext,
            ["Iperf3 error: Connection refused"],
            id="known_error",
        ),
        pytest.param(
            _fail_unexpected,
            lambda: pytest.raises(KeyError),
            [],
            id="unexpected_error",
        ),
        pytest.param(
            _fail_chained,
            lambda: pytest.raises(KeyError),
            [],
            id="chained_error",
        ),
    ],
)
async def test_client_freed_before_next_test_after_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fail: Callable[[object], None],
    expectation: Callable[[], AbstractContextManager[object]],
    logged: list[str],
) -> None:
    """Test that a client is freed before the next test starts after an error.

    Deleting an iperf3 client calls into libiperf. A client kept alive by a
    traceback, logged or raised to the caller, would be deleted later, while
    another host's test runs. Unexpected errors still fail the action.
    """
    alive = 0
    max_alive = 0

    class FakeClient:
        """iperf3 client whose test fails."""

        def __init__(self) -> None:
            nonlocal alive, max_alive
            alive += 1
            max_alive = max(max_alive, alive)

        def __del__(self) -> None:
            nonlocal alive
            alive -= 1

        def run(self) -> None:
            fail(self)

    with patch("homeassistant.components.iperf3.iperf3.Client", FakeClient):
        await setup_iperf3(hass, [HOST_1, HOST_2], manual=True)
        for host in (HOST_1, HOST_2):
            with expectation():
                await _speedtest(hass, host)

    assert max_alive == 1
    assert alive == 0
    for text in logged:
        assert text in caplog.text


async def test_cancelled_speedtest_holds_lock_until_test_ends(
    hass: HomeAssistant, mock_client: MagicMock, blocking_run: BlockingRun
) -> None:
    """Test that cancelling a speedtest caller doesn't cancel its update.

    Stopping a script that waits for the action cancels it, but its test keeps
    running in the executor thread, inside libiperf.
    """
    await setup_iperf3(hass, [HOST_1, HOST_2], manual=True)

    first = _speedtest(hass, HOST_1)
    await blocking_run.async_wait_started(hass)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    # The first host's update still runs, so a new call joins it instead of
    # starting another, and the second host has to wait for it.
    again = _speedtest(hass, HOST_1)
    second = _speedtest(hass, HOST_2)
    await hass.async_add_executor_job(time.sleep, 0.2)
    assert mock_client.run.call_count == 1

    # Cancelling a waiting caller doesn't cancel the queued update either.
    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second

    blocking_run.release.set()
    await again
    await hass.async_block_till_done(wait_background_tasks=True)
    # The sensors refresh in their own executor jobs after the update.
    await hass.async_block_till_done()

    assert blocking_run.max_running == 1
    # Download and upload of both hosts, once each.
    assert mock_client.run.call_count == 4
    assert hass.states.get(DOWNLOAD_ENTITY_ID_2).state == "200.0"


async def test_shutdown_holds_lock_until_test_ends(
    hass: HomeAssistant, mock_client: MagicMock, blocking_run: BlockingRun
) -> None:
    """Test that stopping Home Assistant doesn't let another test start.

    Shutdown cancels the running update, but its test keeps running inside
    libiperf, and an automation on the stop event can still start an update.
    """
    await setup_iperf3(hass, [HOST_1, HOST_2], manual=True)
    stopping = asyncio.Event()

    @callback
    def update_on_stop(event: Event) -> None:
        _speedtest(hass, HOST_2)
        stopping.set()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, update_on_stop)

    first = _speedtest(hass, HOST_1)
    await blocking_run.async_wait_started(hass)
    stop = asyncio.create_task(hass.async_stop())
    async with asyncio.timeout(5):
        await stopping.wait()
    await hass.async_add_executor_job(time.sleep, 0.2)
    assert mock_client.run.call_count == 1

    blocking_run.release.set()
    await stop

    with pytest.raises(asyncio.CancelledError):
        await first
    assert blocking_run.max_running == 1
    # Download and upload of both hosts.
    assert mock_client.run.call_count == 4


async def test_update_after_failing_to_schedule_test(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test that a host can update again after its test failed to be scheduled."""
    await setup_iperf3(hass, [HOST_1, HOST_2], manual=True)

    with (
        patch.object(
            hass,
            "async_add_executor_job",
            side_effect=RuntimeError("cannot schedule new futures after shutdown"),
        ),
        pytest.raises(RuntimeError),
    ):
        await _speedtest(hass, HOST_1)

    async with asyncio.timeout(5):
        for host in (HOST_1, HOST_2):
            await _speedtest(hass, host)
    assert mock_client.run.call_count == 4


async def test_known_error_logged(
    hass: HomeAssistant, mock_client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a connection error is logged without a traceback."""
    await setup_iperf3(hass, [HOST_1], manual=True)
    mock_client.run.side_effect = OSError("Connection refused")

    await _speedtest(hass, HOST_1)
    await hass.async_block_till_done()

    assert "Iperf3 error: Connection refused" in caplog.text
    assert "Traceback" not in caplog.text
    assert hass.states.get(DOWNLOAD_ENTITY_ID_1).state == "unknown"


async def test_scheduled_update_skipped_while_previous_update_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    blocking_run: BlockingRun,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the scan interval skips a host whose update hasn't finished.

    The skip is logged once while updates keep falling behind, e.g. because the
    scan interval is shorter than the tests take, and again after a later stall.
    """
    warning = f"Scheduled updates of {HOST_1} are falling behind"
    await setup_iperf3(hass, [HOST_1], manual=False)

    async def tick() -> None:
        freezer.tick(DEFAULT_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    async def finish() -> None:
        blocking_run.release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        blocking_run.started.clear()
        blocking_run.release.clear()

    async def stall_and_skip() -> None:
        """Start an update that blocks, then fire two more intervals."""
        await tick()
        await blocking_run.async_wait_started(hass)
        await tick()
        await tick()
        await finish()

    await stall_and_skip()
    assert caplog.text.count(warning) == 1
    # Download and upload of the first update only.
    assert mock_client.run.call_count == 2

    # Falling behind again right away isn't logged again.
    await stall_and_skip()
    assert caplog.text.count(warning) == 1
    assert mock_client.run.call_count == 4

    # After an update that kept up, a later stall is reported again.
    blocking_run.release.set()
    await tick()
    await finish()
    await stall_and_skip()
    assert caplog.text.count(warning) == 2
    assert mock_client.run.call_count == 8


async def test_speedtest_waits_for_update_underway(
    hass: HomeAssistant, mock_client: MagicMock, blocking_run: BlockingRun
) -> None:
    """Test that a speedtest joins the host's update that is already running."""
    await setup_iperf3(hass, [HOST_1], manual=True)

    first = _speedtest(hass, HOST_1)
    await blocking_run.async_wait_started(hass)
    second = _speedtest(hass, HOST_1)
    await asyncio.sleep(0)
    assert not second.done()

    blocking_run.release.set()
    await asyncio.gather(first, second)
    # The sensors refresh in their own executor jobs after the update.
    await hass.async_block_till_done()

    # Both callers waited for the same update.
    assert mock_client.run.call_count == 2
    assert hass.states.get(DOWNLOAD_ENTITY_ID_1).state == "200.0"
