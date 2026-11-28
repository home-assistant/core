"""Test the Kodi integration init."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pykodi import InvalidAuthError, TransportError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.kodi.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, HomeAssistant

from . import init_integration, setup_integration
from .util import MockConnection

WATCHDOG_INTERVAL = timedelta(seconds=10)

websocket = pytest.mark.parametrize(
    "can_subscribe", [pytest.param(True, id="websocket")]
)


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    with patch(
        "homeassistant.components.kodi.media_player.async_setup_entry",
        return_value=None,
    ):
        entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_setup_invalid_auth(hass: HomeAssistant) -> None:
    """Test setup fails and starts reauth when login is rejected."""
    with patch.object(
        MockConnection, "connect", side_effect=InvalidAuthError("Unauthorized")
    ):
        entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Login to 1.1.1.1 failed"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


@websocket
async def test_failed_setup_closes_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
) -> None:
    """Test a failed setup closes the connection and drops its subscriptions."""
    mock_kodi.get_application_properties.side_effect = lambda properties: {}

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_connection.close.assert_awaited_once()

    await mock_connection.server.System.OnQuit("xbmc", None)

    mock_connection.close.assert_awaited_once()


@websocket
@pytest.mark.usefixtures("mock_kodi")
async def test_cancelled_setup_closes_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test a setup that is cancelled while it connects closes the connection."""
    connecting = asyncio.Event()

    async def connect() -> None:
        connecting.set()
        await asyncio.Event().wait()

    mock_connection.connect.side_effect = connect
    mock_config_entry.add_to_hass(hass)
    setup = hass.async_create_task(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    async with asyncio.timeout(5):
        await connecting.wait()
        setup.cancel()
        await asyncio.wait([setup])
        await hass.async_block_till_done()

    mock_connection.close.assert_awaited_once()


@websocket
@pytest.mark.usefixtures("mock_kodi")
async def test_home_assistant_stop_closes_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test stopping Home Assistant closes the connection for good."""
    await setup_integration(hass, mock_config_entry)

    await hass.async_stop()

    mock_connection.close.assert_awaited_once()

    freezer.tick(WATCHDOG_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_connection.connect.assert_awaited_once()


@websocket
async def test_home_assistant_stop_during_setup_closes_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test stopping Home Assistant while the setup reads the version."""
    reading = asyncio.Event()
    closed = asyncio.Event()

    async def get_application_properties(properties: list[str]) -> dict:
        reading.set()
        await closed.wait()
        raise TransportError("Connection closed")

    async def close() -> None:
        mock_connection.connected = False
        closed.set()

    mock_kodi.get_application_properties.side_effect = get_application_properties
    mock_connection.close.side_effect = close
    mock_config_entry.add_to_hass(hass)
    setup = hass.async_create_task(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    async with asyncio.timeout(5):
        await reading.wait()
        hass.set_state(CoreState.stopping)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        assert await setup

    mock_connection.close.assert_awaited_once()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert "Unable to remove unknown job listener" not in caplog.text
    mock_connection.connect.assert_awaited_once()


@websocket
async def test_unload_before_home_assistant_started(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an entry unloaded during startup does not connect once started."""
    hass.set_state(CoreState.not_running)
    await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    freezer.tick(WATCHDOG_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_connection.connect.assert_awaited_once()
    mock_kodi.ping.assert_not_awaited()


@websocket
@pytest.mark.usefixtures("mock_kodi")
async def test_pending_reconnect_does_not_block(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a pending reconnect does not hold up waiting for Home Assistant."""
    await setup_integration(hass, mock_config_entry)
    connecting = asyncio.Event()

    async def connect() -> None:
        connecting.set()
        await asyncio.Event().wait()

    mock_connection.connected = False
    mock_connection.connect.side_effect = connect
    freezer.tick(WATCHDOG_INTERVAL)
    async_fire_time_changed(hass)
    async with asyncio.timeout(1):
        await connecting.wait()
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


@websocket
@pytest.mark.usefixtures("mock_kodi")
async def test_unload_while_reconnecting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading ends a pending reconnect before it closes the connection."""
    await setup_integration(hass, mock_config_entry)
    connecting = asyncio.Event()
    calls: list[str] = []

    async def connect() -> None:
        connecting.set()
        try:
            await asyncio.Event().wait()
        finally:
            calls.append("connect ended")

    async def close() -> None:
        calls.append("close")

    mock_connection.connected = False
    mock_connection.connect.side_effect = connect
    mock_connection.close.side_effect = close
    freezer.tick(WATCHDOG_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    assert connecting.is_set()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert calls == ["connect ended", "close"]


async def test_http_connection_has_no_watchdog(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an entry without websocket only polls Kodi."""
    await setup_integration(hass, mock_config_entry)
    mock_kodi.get_application_properties.assert_not_awaited()

    freezer.tick(WATCHDOG_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_connection.subscribe.assert_not_called()
    mock_kodi.ping.assert_not_awaited()
