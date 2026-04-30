"""Test the CatGenie sensor platform."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ENTRY_DATA

from tests.common import MockConfigEntry


async def test_sensors_created(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test that sensor entities are created for each device."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Check key sensors exist
    state = hass.states.get("sensor.catgenie_litter_box_sani_solution_remaining")
    assert state is not None
    assert state.state == "75"

    state = hass.states.get("sensor.catgenie_litter_box_status")
    assert state is not None
    assert state.state == "cleaning"

    state = hass.states.get("sensor.catgenie_litter_box_clean_progress")
    assert state is not None
    assert state.state == "42"


async def test_sensor_device_removed(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test sensor returns None when device disappears from coordinator data."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Device disappears from the API response
    mock_catgenie_client.get_devices.return_value = []

    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Entity is marked unavailable because available returns False
    state = hass.states.get("sensor.catgenie_litter_box_sani_solution_remaining")
    assert state is not None
    assert state.state == "unavailable"

    # Verify native_value returns None directly when device_data is gone
    entity_id = "sensor.catgenie_litter_box_sani_solution_remaining"
    entity = hass.data["entity_components"]["sensor"].get_entity(entity_id)
    assert entity is not None
    assert entity.native_value is None
