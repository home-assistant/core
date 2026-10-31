"""Test the AlarmDecoder integration setup."""

import asyncio
from collections.abc import Callable, Generator
from datetime import timedelta
import threading
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

from alarmdecoder.util import NoDeviceError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.alarmdecoder.const import DOMAIN, PROTOCOL_SOCKET
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


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
        patch("homeassistant.components.alarmdecoder.PLATFORMS", []),
    ):
        yield controllers[0]


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


async def test_setup_timeout_cancels_pending_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test a timed-out setup doesn't leave its reconnect timer running."""
    mock_controller.open.side_effect = NoDeviceError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_controller.open.call_count == 1

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()

    # The 5 second reconnect of the abandoned attempt must not run.
    assert mock_controller.open.call_count == 1


async def test_unload_cancels_pending_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test unloading while reconnecting stops the old controller for good."""
    mock_controller.is_init = AsyncMock(return_value=True)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # The connection drops and the first reconnect attempt fails.
    mock_controller.open.side_effect = NoDeviceError
    mock_controller.open.reset_mock()
    mock_controller.on_close[0](None)
    await hass.async_block_till_done()
    assert mock_controller.open.call_count == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()

    assert mock_controller.open.call_count == 1


@pytest.mark.parametrize("attempt_fails", [False, True])
async def test_unload_during_reconnect_attempt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
    attempt_fails: bool,
) -> None:
    """Test a reconnect still connecting at unload doesn't revive the controller."""
    mock_controller.is_init = AsyncMock(return_value=True)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # The connection drops and the reconnect attempt hangs in connect(). A plain
    # function rather than a mock, so it runs in a worker thread like the real one.
    started, release = threading.Event(), threading.Event()
    attempts: list[int | None] = []
    events: list[str] = []

    def slow_open(baud: int | None) -> None:
        attempts.append(baud)
        started.set()
        release.wait(5)
        events.append("opened")
        if attempt_fails:
            raise NoDeviceError

    mock_controller.open = slow_open
    mock_controller.close.side_effect = lambda: events.append("closed")
    mock_controller.on_close[0](None)
    assert await hass.async_add_executor_job(started.wait, 5)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    # Closing now couldn't interrupt the connect.
    assert events == []

    # The attempt finishes after the unload, and its socket then closes.
    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    for handler in mock_controller.on_close:
        handler(None)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()

    assert len(attempts) == 1
    # Closed once the attempt finished, so a connection it made doesn't linger.
    assert events == ["opened", "closed"]


async def test_setup_timeout_during_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
) -> None:
    """Test a connect outlasting the setup timeout is closed when it finishes."""
    release = threading.Event()
    events: list[str] = []

    def slow_open(baud: int | None) -> None:
        release.wait(5)
        events.append("opened")

    mock_controller.open = slow_open
    mock_controller.close.side_effect = lambda: events.append("closed")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert events == []

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert events == ["opened", "closed"]
