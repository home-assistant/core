"""Test the ISS sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.iss.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_sensor_created(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensor entity is created."""
    state = hass.states.get("sensor.iss")
    assert state is not None
    assert state.state == "7"


async def test_sensor_attributes_show_on_map_false(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensor attributes when show_on_map is False."""
    state = hass.states.get("sensor.iss")
    assert state is not None
    assert state.state == "7"
    assert state.attributes["lat"] == "40.271698"
    assert state.attributes["long"] == "15.619478"
    # Should NOT have ATTR_LATITUDE/ATTR_LONGITUDE when show_on_map is False
    assert ATTR_LATITUDE not in state.attributes
    assert ATTR_LONGITUDE not in state.attributes


async def test_sensor_attributes_show_on_map_true(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pyiss: MagicMock
) -> None:
    """Test sensor attributes when show_on_map is True."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_SHOW_ON_MAP: True}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.iss")
    assert state is not None
    assert state.state == "7"
    # Should have ATTR_LATITUDE/ATTR_LONGITUDE when show_on_map is True
    assert state.attributes[ATTR_LATITUDE] == "40.271698"
    assert state.attributes[ATTR_LONGITUDE] == "15.619478"
    # Should NOT have lat/long keys
    assert "lat" not in state.attributes
    assert "long" not in state.attributes


async def test_sensor_device_info(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensor has correct device info."""
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get("sensor.iss")

    assert entity is not None
    assert entity.unique_id == f"{init_integration.entry_id}_people"

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entity.device_id)

    assert device is not None
    assert device.name == DEFAULT_NAME
    assert (DOMAIN, init_integration.entry_id) in device.identifiers


async def test_sensor_updates_with_coordinator(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_pyiss: MagicMock
) -> None:
    """Test sensor updates when coordinator data changes."""
    state = hass.states.get("sensor.iss")
    assert state.state == "7"

    # Update mock data
    mock_pyiss.number_of_people_in_space.return_value = 10
    mock_pyiss.current_location.return_value = {
        "latitude": "50.0",
        "longitude": "-100.0",
    }

    # Trigger coordinator refresh
    coordinator = init_integration.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check sensor updated
    state = hass.states.get("sensor.iss")
    assert state.state == "10"
    assert state.attributes["lat"] == "50.0"
    assert state.attributes["long"] == "-100.0"
