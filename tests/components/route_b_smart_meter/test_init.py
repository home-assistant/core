"""Tests for the Smart Meter B Route integration init."""

from freezegun.api import FrozenDateTimeFactory

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


async def test_async_update_recovery_from_reopen(
    hass: HomeAssistant,
    mock_momonga,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test auto-recovery when MomongaNeedToReopen is raised."""
    from momonga.momonga_exception import MomongaNeedToReopen

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.get_instantaneous_current.side_effect = [
        MomongaNeedToReopen("test"),
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
    assert client.open.call_count == 2
