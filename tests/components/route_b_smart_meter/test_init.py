"""Tests for the Smart Meter B Route integration init."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from momonga import MomongaError
from momonga.momonga_exception import MomongaNeedToReopen

from homeassistant.components.route_b_smart_meter.const import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_momonga: Mock, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_async_update_recovery_from_reopen(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test auto-recovery when MomongaNeedToReopen is raised."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.get_instantaneous_current.side_effect = [
        MomongaNeedToReopen("session expired"),
        {"r phase current": 5, "t phase current": 6},
    ]

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(
        "sensor.route_b_smart_meter_01234567890123456789012345f789"
        "_instantaneous_current_r_phase"
    )
    assert entity is not None
    assert entity.state != STATE_UNAVAILABLE
    assert entity.state == "5"
    # open() called once at setup + once for reopen
    assert client.open.call_count == 2


async def test_async_update_recovery_from_transient_error(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test recovery when reopen itself raises a transient MomongaError."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    # First _get_data raises NeedToReopen, first reopen+_get_data also
    # fails with a generic MomongaError, second reopen succeeds
    client.get_instantaneous_current.side_effect = [
        MomongaNeedToReopen("session expired"),
        MomongaError("serial port busy"),
        {"r phase current": 7, "t phase current": 8},
    ]

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(
        "sensor.route_b_smart_meter_01234567890123456789012345f789"
        "_instantaneous_current_r_phase"
    )
    assert entity is not None
    assert entity.state != STATE_UNAVAILABLE
    assert entity.state == "7"
    # open() called once at setup + twice for reopen attempts
    assert client.open.call_count == 3


async def test_async_update_recovery_exhausted(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that entities go unavailable when all recovery attempts fail."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    # Initial _get_data raises NeedToReopen, all retry _get_data calls also fail
    client.get_instantaneous_current.side_effect = MomongaNeedToReopen(
        "permanent failure"
    )

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(
        "sensor.route_b_smart_meter_01234567890123456789012345f789"
        "_instantaneous_current_r_phase"
    )
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE
