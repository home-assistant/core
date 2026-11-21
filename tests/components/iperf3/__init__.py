"""Tests for the iperf3 integration."""

import threading
from unittest.mock import MagicMock

from homeassistant.components.iperf3.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

HOST_1 = "192.168.1.10"
HOST_2 = "192.168.1.11"


def make_result() -> MagicMock:
    """Return a successful iperf3 test result."""
    return MagicMock(error=None, received_Mbps=200.0, sent_Mbps=100.0, version="3.20")


class BlockingRun:
    """Side effect for the client's run() that blocks until released."""

    def __init__(self, hold: float = 5) -> None:
        """Initialize the side effect, blocking each test for at most hold seconds."""
        self._hold = hold
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
        self.release.wait(self._hold)
        with self._lock:
            self._running -= 1
        return make_result()

    async def async_wait_started(self, hass: HomeAssistant) -> None:
        """Wait until a test has started, without blocking the event loop."""
        assert await hass.async_add_executor_job(self.started.wait, 5)


async def setup_iperf3(hass: HomeAssistant, hosts: list[str], manual: bool) -> None:
    """Set up the iperf3 integration for the given hosts."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"hosts": [{"host": host} for host in hosts], "manual": manual}},
    )
    await hass.async_block_till_done()
