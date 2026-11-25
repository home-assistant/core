"""Test the AlarmDecoder integration setup."""

import asyncio
from collections.abc import Callable, Generator
import threading
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

from alarmdecoder.util import NoDeviceError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.alarmdecoder.const import DOMAIN, PROTOCOL_SOCKET
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a socket AlarmDecoder config entry added to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PROTOCOL: PROTOCOL_SOCKET,
            CONF_HOST: "alarmdecoder123",
            CONF_PORT: 10001,
        },
    )
    entry.add_to_hass(hass)
    return entry


class Handlers(list):
    """Stand-in for an alarmdecoder event: `+=` adds a handler."""

    def __iadd__(self, handler: Callable[..., None]) -> Self:
        """Add a handler."""
        self.append(handler)
        return self


def _make_controller() -> MagicMock:
    """Return a controller mock that never answers the version request."""
    controller = MagicMock()
    controller.is_init = AsyncMock(side_effect=asyncio.Event().wait)
    for event in (
        "on_message",
        "on_rfx_message",
        "on_zone_fault",
        "on_zone_restore",
        "on_close",
        "on_expander_message",
    ):
        setattr(controller, event, Handlers())
    return controller


@pytest.fixture
def mock_controller() -> Generator[MagicMock]:
    """Patch AdExt; return the controller of the first setup attempt.

    Later attempts (Home Assistant's own setup retries) get fresh controllers,
    so the first one's calls only count what that attempt left behind.
    """
    controllers = [_make_controller() for _ in range(5)]
    with (
        patch("homeassistant.components.alarmdecoder.AdExt", side_effect=controllers),
        patch("homeassistant.components.alarmdecoder.INIT_TIMEOUT", 0.5),
        patch("homeassistant.components.alarmdecoder.RECONNECT_DELAY", 0.01),
        patch("homeassistant.components.alarmdecoder.PLATFORMS", []),
    ):
        yield controllers[0]


class SlowConnect:
    """A connect() that hangs until released, in a worker thread like the real one.

    Used as a plain object rather than a mock, which would run on the event loop.
    """

    def __init__(self, controller: MagicMock, fails: bool = False) -> None:
        """Replace the controller's open and close."""
        self.started = threading.Event()
        self.release = threading.Event()
        self.closed = threading.Event()
        self.fails = fails
        self.attempts = 0
        self.events: list[str] = []
        controller.open = self.open
        controller.close.side_effect = self.close

    def open(self, baud: int | None) -> None:
        """Hang, then finish."""
        self.attempts += 1
        self.started.set()
        self.release.wait(10)
        self.events.append("opened")
        if self.fails:
            raise NoDeviceError

    def close(self) -> None:
        """Record the close."""
        self.events.append("closed")
        self.closed.set()


async def _async_setup_connected(
    hass: HomeAssistant, entry: MockConfigEntry, controller: MagicMock
) -> None:
    """Set up the entry with a device that answers."""
    controller.is_init = AsyncMock(return_value=True)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_retries_without_version_reply(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test setup gives up and retries when the device never answers."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_controller.close.assert_called_once()
    assert not mock_config_entry.update_listeners


async def test_setup_retries_when_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test setup gives up right away when the device can't be reached."""
    mock_controller.open.side_effect = NoDeviceError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_controller.open.assert_called_once()
    mock_controller.close.assert_called_once()
    assert not mock_config_entry.update_listeners


async def test_reconnects_after_lost_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test every lost connection is retried until connected again."""
    await _async_setup_connected(hass, mock_config_entry, mock_controller)
    mock_controller.open.reset_mock()
    # The first reconnect attempt fails, the second one connects.
    mock_controller.open.side_effect = [NoDeviceError, None, None]

    mock_controller.on_close[0](None)
    await hass.async_block_till_done()
    await asyncio.sleep(0.05)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_controller.open.call_count == 2

    mock_controller.on_close[0](None)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_controller.open.call_count == 3


async def test_unload_stops_reconnecting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test unloading while reconnecting stops the old controller for good."""
    await _async_setup_connected(hass, mock_config_entry, mock_controller)
    mock_controller.open.reset_mock()
    mock_controller.open.side_effect = NoDeviceError

    mock_controller.on_close[0](None)
    await hass.async_block_till_done()
    await asyncio.sleep(0.05)
    assert mock_controller.open.call_count > 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    attempts = mock_controller.open.call_count

    await asyncio.sleep(0.05)
    assert mock_controller.open.call_count == attempts
    mock_controller.close.assert_called_once()


@pytest.mark.parametrize("fails", [False, True])
async def test_unload_during_reconnect_attempt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
    fails: bool,
) -> None:
    """Test a reconnect still connecting at unload is closed when it finishes."""
    await _async_setup_connected(hass, mock_config_entry, mock_controller)
    connect = SlowConnect(mock_controller, fails)

    mock_controller.on_close[0](None)
    assert await hass.async_add_executor_job(connect.started.wait, 5)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    # Closing now couldn't interrupt the connect.
    assert connect.events == []

    connect.release.set()
    assert await hass.async_add_executor_job(connect.closed.wait, 5)
    await asyncio.sleep(0.05)

    assert connect.attempts == 1
    assert connect.events == ["opened", "closed"]


@pytest.mark.parametrize("fails", [False, True])
async def test_setup_timeout_during_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
    fails: bool,
) -> None:
    """Test a connect outlasting the setup timeout is closed when it finishes."""
    connect = SlowConnect(mock_controller, fails)

    # A tracked task, like bootstrap's setup: this is what startup waits for.
    hass.async_create_task(hass.config_entries.async_setup(mock_config_entry.entry_id))
    try:
        assert await hass.async_add_executor_job(connect.started.wait, 5)
        async with asyncio.timeout(3):
            await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
        assert connect.events == []
    finally:
        connect.release.set()

    assert await hass.async_add_executor_job(connect.closed.wait, 5)
    await asyncio.sleep(0.05)
    assert connect.events == ["opened", "closed"]


async def test_reconnect_attempt_does_not_hold_up_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test Home Assistant doesn't wait for a reconnect that is still connecting."""
    await _async_setup_connected(hass, mock_config_entry, mock_controller)
    connect = SlowConnect(mock_controller)

    mock_controller.on_close[0](None)
    try:
        assert await hass.async_add_executor_job(connect.started.wait, 5)
        async with asyncio.timeout(3):
            await hass.async_block_till_done()
    finally:
        connect.release.set()


async def test_connect_finishing_after_its_future_was_cancelled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test the close still waits for connect() if stopping cancels the future."""
    connect = SlowConnect(mock_controller)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    # What hass.async_stop() does to background tasks and executor jobs.
    for task in list(hass._background_tasks):
        task.cancel("Home Assistant is stopping")
    await asyncio.sleep(0.05)
    assert connect.events == []

    connect.release.set()
    assert await hass.async_add_executor_job(connect.closed.wait, 5)
    await asyncio.sleep(0.05)
    assert connect.events == ["opened", "closed"]


async def test_stop_then_unload_closes_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test a second close is skipped, as the library raises on one."""
    await _async_setup_connected(hass, mock_config_entry, mock_controller)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_controller.close.assert_called_once()
