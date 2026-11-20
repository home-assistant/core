"""Tests for the iperf3 integration setup and test scheduling."""

from collections.abc import Generator
import threading
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.iperf3.const import DEFAULT_INTERVAL, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

HOST_1 = "192.168.1.10"
HOST_2 = "192.168.1.11"


def _result() -> MagicMock:
    """Return a successful iperf3 test result."""
    return MagicMock(error=None, received_Mbps=200.0, sent_Mbps=100.0, version="3.20")


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the iperf3 client."""
    with patch("homeassistant.components.iperf3.iperf3.Client") as client_cls:
        client_cls.return_value.run.return_value = _result()
        yield client_cls.return_value


async def _setup(hass: HomeAssistant, hosts: list[str], manual: bool) -> None:
    """Set up the iperf3 integration for the given hosts."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"hosts": [{"host": host} for host in hosts], "manual": manual}},
    )
    await hass.async_block_till_done()


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
        return _result()

    await _setup(hass, [HOST_1, HOST_2], manual=False)
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
        return _result()

    await _setup(hass, [HOST_1], manual=True)
    mock_client.run.side_effect = run

    async def speedtest() -> None:
        await hass.services.async_call(
            DOMAIN, "speedtest", {"host": HOST_1}, blocking=True
        )

    first = hass.async_create_task(speedtest())
    assert await hass.async_add_executor_job(started.wait, 5)

    await speedtest()
    assert mock_client.run.call_count == 1
    assert f"previous iperf3 test of {HOST_1} is still running" in caplog.text

    release.set()
    await first
    # Download and upload of the first update only.
    assert mock_client.run.call_count == 2
