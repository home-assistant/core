"""Test Rejseplanen sensors."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_sensors_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor unique IDs."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Main integration without subentries creates no entities
    assert len(entity_entries) == 0


@pytest.mark.usefixtures("init_integration")
async def test_service_device_created(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service integration creates a device."""
    # Service integrations create a main device entry
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    # Should have exactly one device for the service
    assert len(device_entries) == 1

    device = device_entries[0]
    assert device.name == "Rejseplanen"
    assert device.manufacturer == "Rejseplanen"
    assert device.entry_type is dr.DeviceEntryType.SERVICE


@pytest.mark.usefixtures("init_integration")
async def test_no_entities_without_subentries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test main integration creates no entities without stop subentries."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Main integration should not create entities - only subentries do
    assert len(entity_entries) == 0


async def test_integration_loads_successfully(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration loads successfully without stops."""
    mock_config_entry.add_to_hass(hass)

    # Mock the API to return empty data (no stops configured)
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_departures.return_value = ([], [])
        mock_api_class.return_value = mock_api

        # Set up the main integration
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Integration should load successfully even without stops
    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Verify no sensor entities were created
    states = hass.states.async_all()
    rejseplanen_entities = [
        state
        for state in states
        if state.entity_id.startswith("sensor.") and "rejseplanen" in state.entity_id
    ]

    # This integration uses subentries, so no sensors should exist without stops configured
    assert len(rejseplanen_entities) == 0, (
        "No entities should exist without stop subentries"
    )
