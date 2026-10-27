"""Tests for setting the Spin EV Charger integration up and polling it."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from spinev_ble import ChargerStatus, SpinEvError

from homeassistant.components.spin_ble.const import (
    CHARGING_INTERVAL,
    CONF_CONNECTION_MODE,
    IDLE_INTERVAL,
    ConnectionMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration, setup_persistent
from .const import IDLE_STATUS, STATE_SENSOR, STATUS


@pytest.mark.usefixtures("mock_charger")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads, then unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_charger")
async def test_setup_retries_when_the_charger_is_not_seen(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """An address the Bluetooth manager cannot resolve is a retry, not a failure."""
    mock_ble_device.return_value = None
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_the_first_read_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_charger: AsyncMock
) -> None:
    """A charger that does not answer on setup is a retry, not a failure."""
    mock_charger.async_get_status.side_effect = SpinEvError("no reply")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("status", "interval"),
    [
        pytest.param(STATUS, CHARGING_INTERVAL, id="charging"),
        pytest.param(IDLE_STATUS, IDLE_INTERVAL, id="idle"),
    ],
)
async def test_the_poll_interval_follows_the_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
    status: ChargerStatus,
    interval: timedelta,
) -> None:
    """Polling is fast during a session and slow while idle."""
    mock_charger.async_get_status.return_value = status
    await setup_integration(hass, mock_config_entry)
    mock_charger.async_get_status.reset_mock()

    freezer.tick(interval / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_charger.async_get_status.assert_not_awaited()

    freezer.tick(interval / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_charger.async_get_status.assert_awaited_once()


async def test_a_per_poll_connection_is_released(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_charger: AsyncMock
) -> None:
    """The default mode hands the charger back so the phone app can reach it."""
    await setup_integration(hass, mock_config_entry)

    mock_charger.async_disconnect.assert_awaited()


async def test_a_persistent_connection_is_held(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_charger: AsyncMock
) -> None:
    """Holding the charger's only Bluetooth slot keeps everyone else out."""
    await setup_persistent(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_charger.async_disconnect.assert_not_awaited()


async def test_a_held_link_is_released_on_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_charger: AsyncMock
) -> None:
    """Unloading hands the charger back even when the link was being held."""
    await setup_persistent(hass, mock_config_entry)

    mock_charger.async_disconnect.assert_not_awaited()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_charger.async_disconnect.assert_awaited()


async def test_a_held_link_is_released_on_stop(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_charger: AsyncMock
) -> None:
    """Stopping Home Assistant hands the charger back, as no unload runs then."""
    await setup_persistent(hass, mock_config_entry)

    mock_charger.async_disconnect.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_charger.async_disconnect.assert_awaited_once()


async def test_a_held_link_that_drops_is_rebuilt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """In persistent mode the client outlives a poll, so a dead one is replaced."""
    await setup_persistent(hass, mock_config_entry)

    mock_charger.is_connected = False
    freezer.tick(CHARGING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_charger.async_disconnect.assert_awaited()
    assert hass.states.get(STATE_SENSOR).state == "charging"


async def test_a_held_link_recovers_from_a_failed_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """In persistent mode a failed read drops the link, and the next poll reconnects."""
    await setup_persistent(hass, mock_config_entry)

    mock_charger.async_get_status.side_effect = SpinEvError("gone")
    freezer.tick(CHARGING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_charger.async_disconnect.assert_awaited_once()
    assert hass.states.get(STATE_SENSOR).state == STATE_UNAVAILABLE

    mock_charger.async_get_status.side_effect = None
    mock_charger.async_connect.reset_mock()
    freezer.tick(CHARGING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_charger.async_connect.assert_awaited_once()
    assert hass.states.get(STATE_SENSOR).state == "charging"


async def test_a_changed_connection_mode_takes_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The mode is read when the coordinator is built, so it needs a reload."""
    await setup_integration(hass, mock_config_entry)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_CONNECTION_MODE: ConnectionMode.PERSISTENT,
        },
    )
    await hass.async_block_till_done()

    mock_charger.async_disconnect.reset_mock()
    freezer.tick(CHARGING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_charger.async_disconnect.assert_not_awaited()


async def test_a_failed_poll_makes_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A charger that stops answering is reported as unavailable, not stale."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(STATE_SENSOR).state != STATE_UNAVAILABLE

    mock_charger.async_get_status.side_effect = SpinEvError("gone")
    freezer.tick(CHARGING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(STATE_SENSOR).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_charger")
async def test_a_poll_fails_when_the_charger_goes_out_of_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An address the Bluetooth manager stops resolving fails the poll."""
    await setup_integration(hass, mock_config_entry)

    mock_ble_device.return_value = None
    freezer.tick(CHARGING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(STATE_SENSOR).state == STATE_UNAVAILABLE
