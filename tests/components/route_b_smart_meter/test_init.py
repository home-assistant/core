"""Tests for the Smart Meter B Route integration init."""

from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from momonga import MomongaError
from momonga.momonga_exception import MomongaNeedToReopen

from homeassistant.components.route_b_smart_meter.const import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_momonga, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_recovery_from_reopen(
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

    with patch("homeassistant.components.route_b_smart_meter.coordinator.time.sleep"):
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


async def test_recovery_from_transient_error(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test recovery when reopen raises a transient MomongaError."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.get_instantaneous_current.side_effect = [
        MomongaNeedToReopen("session expired"),
        MomongaError("serial port busy"),
        {"r phase current": 7, "t phase current": 8},
    ]

    with patch("homeassistant.components.route_b_smart_meter.coordinator.time.sleep"):
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
    # open() at setup + 2 reopen attempts
    assert client.open.call_count == 3


async def test_recovery_exhausted(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities go unavailable when all recovery attempts fail."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.get_instantaneous_current.side_effect = MomongaNeedToReopen(
        "permanent failure"
    )

    with patch("homeassistant.components.route_b_smart_meter.coordinator.time.sleep"):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(
        "sensor.route_b_smart_meter_01234567890123456789012345f789"
        "_instantaneous_current_r_phase"
    )
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE
    # open() at setup + 5 exhausted reopen attempts
    assert client.open.call_count == 6


async def test_recovery_from_serial_error(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test recovery when USB disconnect causes OSError instead of MomongaError."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.get_instantaneous_current.side_effect = [
        OSError("device disconnected"),
        {"r phase current": 10, "t phase current": 11},
    ]

    with patch("homeassistant.components.route_b_smart_meter.coordinator.time.sleep"):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(
        "sensor.route_b_smart_meter_01234567890123456789012345f789"
        "_instantaneous_current_r_phase"
    )
    assert entity is not None
    assert entity.state != STATE_UNAVAILABLE
    assert entity.state == "10"
    # open() called once at setup + once for reopen
    assert client.open.call_count == 2
