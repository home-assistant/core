"""Tests for setting the Spin EV Charger integration up and polling it."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from spinev_ble import ChargerStatus, SpinEvError

from homeassistant.components.spinev.const import (
    CHARGING_INTERVAL,
    CONF_CONNECTION_MODE,
    IDLE_INTERVAL,
    ConnectionMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import IDLE_STATUS, STATE_SENSOR, STATUS

from tests.common import MockConfigEntry, async_fire_time_changed


async def setup_persistent(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the integration up with the charger's Bluetooth slot held open."""
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, CONF_CONNECTION_MODE: ConnectionMode.PERSISTENT},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


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
    ("status", "expected"),
    [
        pytest.param(STATUS, CHARGING_INTERVAL, id="charging"),
        pytest.param(IDLE_STATUS, IDLE_INTERVAL, id="idle"),
    ],
)
async def test_the_poll_interval_follows_the_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    status: ChargerStatus,
    expected: timedelta,
) -> None:
    """Polling is fast during a session and slow while idle."""
    mock_charger.async_get_status.return_value = status
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.runtime_data.update_interval == expected


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


async def test_a_held_link_that_drops_is_rebuilt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """In persistent mode the client outlives a poll, so a dead one is replaced."""
    await setup_persistent(hass, mock_config_entry)

    mock_charger.is_connected = False
    freezer.tick(CHARGING_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_charger.async_disconnect.assert_awaited()
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
    freezer.tick(CHARGING_INTERVAL + timedelta(seconds=1))
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
    freezer.tick(CHARGING_INTERVAL + timedelta(seconds=1))
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
    freezer.tick(CHARGING_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(STATE_SENSOR).state == STATE_UNAVAILABLE
