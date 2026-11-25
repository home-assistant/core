"""Tests for the Roomba periodic connection mode."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from roombapy import RoombaConnectionError, RoombaError

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.roomba.const import (
    COMMAND_HOLD_SECONDS,
    CONF_CONTINUOUS,
    PERIODIC_UPDATE_INTERVAL,
    TELEMETRY_SETTLE_SECONDS,
)
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN, SERVICE_LOCATE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

VACUUM_ENTITY_ID = "vacuum.test_roomba"


@pytest.fixture
def periodic_roomba(mock_roomba: AsyncMock) -> AsyncMock:
    """Make connect and disconnect toggle the connected flag."""

    async def _connect() -> None:
        mock_roomba.connected = True

    async def _disconnect() -> None:
        mock_roomba.connected = False

    mock_roomba.connect.side_effect = _connect
    mock_roomba.disconnect.side_effect = _disconnect
    return mock_roomba


def _set_phase(roomba: AsyncMock, phase: str) -> None:
    roomba.master_state["state"]["reported"]["cleanMissionStatus"]["phase"] = phase


async def _setup(
    hass: HomeAssistant, entry: MockConfigEntry, *, continuous: bool
) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_CONTINUOUS: continuous})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_periodic_releases_robot_after_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test the session is closed once the initial telemetry has arrived."""
    await _setup(hass, mock_config_entry, continuous=False)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    periodic_roomba.disconnect.assert_not_awaited()

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))

    periodic_roomba.disconnect.assert_awaited_once()
    assert not periodic_roomba.connected
    # The last known state stays visible while disconnected.
    assert hass.states.get(VACUUM_ENTITY_ID).state == "docked"


async def test_periodic_poll_reconnects_and_releases(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test each poll opens a short-lived session."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))
    assert periodic_roomba.connect.await_count == 1

    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert periodic_roomba.connect.await_count == 2
    assert periodic_roomba.connected

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))
    assert not periodic_roomba.connected


async def test_periodic_keeps_session_during_mission(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test the session stays open while cleaning and closes once docked."""
    _set_phase(periodic_roomba, "run")
    await _setup(hass, mock_config_entry, continuous=False)

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    periodic_roomba.disconnect.assert_not_awaited()
    assert periodic_roomba.connect.await_count == 1

    _set_phase(periodic_roomba, "charge")
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    periodic_roomba.disconnect.assert_awaited_once()


async def test_periodic_command_connects_and_holds(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a command reconnects and the session is held for a while."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))
    assert not periodic_roomba.connected

    await hass.services.async_call(
        VACUUM_DOMAIN, SERVICE_LOCATE, {ATTR_ENTITY_ID: VACUUM_ENTITY_ID}, blocking=True
    )
    assert periodic_roomba.connect.await_count == 2
    periodic_roomba.send_command.assert_awaited_once_with("find", None)

    await _advance(hass, freezer, timedelta(seconds=COMMAND_HOLD_SECONDS - 1))
    assert periodic_roomba.connected

    await _advance(hass, freezer, timedelta(seconds=1))
    assert not periodic_roomba.connected


async def test_periodic_poll_failure_retries(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test an unreachable robot during a poll is retried on the next one."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))

    connect = periodic_roomba.connect.side_effect
    periodic_roomba.connect.side_effect = RoombaConnectionError
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not periodic_roomba.connected

    periodic_roomba.connect.side_effect = connect
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert periodic_roomba.connect.await_count == 3
    assert periodic_roomba.connected


async def test_continuous_never_releases(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test continuous mode holds a single session."""
    await _setup(hass, mock_config_entry, continuous=True)

    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL * 3)

    periodic_roomba.connect.assert_awaited_once()
    periodic_roomba.disconnect.assert_not_awaited()


async def test_options_flow_switches_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test turning continuous off reloads into periodic mode."""
    await _setup(hass, mock_config_entry, continuous=True)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_CONTINUOUS: False}
    )
    await hass.async_block_till_done()

    assert mock_config_entry.options == {CONF_CONTINUOUS: False}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    disconnects = periodic_roomba.disconnect.await_count

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))
    assert periodic_roomba.disconnect.await_count == disconnects + 1


async def test_polling_disabled_refreshes_on_request(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test that with polling disabled only update_entity opens a session."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_CONTINUOUS: False},
        pref_disable_polling=True,
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))
    assert not periodic_roomba.connected

    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL * 3)
    periodic_roomba.connect.assert_awaited_once()

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: VACUUM_ENTITY_ID},
        blocking=True,
    )
    assert periodic_roomba.connect.await_count == 2
    assert periodic_roomba.connected

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))
    assert not periodic_roomba.connected


async def test_refresh_does_not_cut_telemetry_short(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a second refresh right after a reconnect keeps the session open."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))

    for _ in range(2):
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: VACUUM_ENTITY_ID},
            blocking=True,
        )
    assert periodic_roomba.connect.await_count == 2
    assert periodic_roomba.connected

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))
    assert not periodic_roomba.connected


async def test_unreachable_is_logged_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test losing and regaining the robot is logged once each."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))

    connect = periodic_roomba.connect.side_effect
    periodic_roomba.connect.side_effect = RoombaConnectionError
    for _ in range(3):
        await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert caplog.text.count("is unreachable") == 1

    periodic_roomba.connect.side_effect = connect
    for _ in range(2):
        await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
        await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))
    assert caplog.text.count("is reachable again") == 1


async def test_reconnect_after_dropped_session(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a session that dropped on its own is torn down before reconnecting."""
    reconnecting = False

    async def _connect() -> None:
        if reconnecting:
            raise RoombaError("Already connected")
        periodic_roomba.connected = True

    async def _disconnect() -> None:
        nonlocal reconnecting
        reconnecting = False
        periodic_roomba.connected = False

    periodic_roomba.connect.side_effect = _connect
    periodic_roomba.disconnect.side_effect = _disconnect
    _set_phase(periodic_roomba, "run")
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))

    # Wi-Fi drop mid-mission: the client is reconnecting in the background.
    periodic_roomba.connected = False
    reconnecting = True
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert periodic_roomba.connected

    periodic_roomba.connected = False
    reconnecting = True
    await hass.services.async_call(
        VACUUM_DOMAIN, SERVICE_LOCATE, {ATTR_ENTITY_ID: VACUUM_ENTITY_ID}, blocking=True
    )
    periodic_roomba.send_command.assert_awaited_once_with("find", None)


async def test_idle_release_stops_background_reconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a session that dropped while idle is torn down, not left retrying."""
    await _setup(hass, mock_config_entry, continuous=False)
    # Dropped on its own; the client would keep reconnecting in the background.
    periodic_roomba.connected = False

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_SETTLE_SECONDS))

    periodic_roomba.disconnect.assert_awaited_once()


async def test_no_session_after_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a late command does not reopen a session once the entry is stopped."""
    await _setup(hass, mock_config_entry, continuous=False)
    connection = mock_config_entry.runtime_data.connection
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not periodic_roomba.connected

    await connection.async_ensure_connected()

    periodic_roomba.connect.assert_awaited_once()
    assert not periodic_roomba.connected
