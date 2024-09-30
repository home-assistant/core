"""Tests for the Appartme climate platform."""

from unittest.mock import patch

from homeassistant.components.appartme.const import DOMAIN
from homeassistant.components.climate import PRESET_COMFORT, PRESET_ECO, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE

from tests.common import MockConfigEntry


async def test_climate_entity(hass, mock_appartme_api):
    """Test the Appartme climate entity."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": {"access_token": "test-access-token"}},
    )
    config_entry.add_to_hass(hass)

    # Mock API responses
    device_id = "device123"
    mock_appartme_api.fetch_devices.return_value = [
        {"deviceId": device_id, "type": "mm", "name": "Main Module"}
    ]
    mock_appartme_api.fetch_device_details.return_value = {
        "deviceId": device_id,
        "type": "mm",
        "name": "Main Module",
        "properties": [
            {"propertyId": "thermostat_mode", "mode": "readwrite"},
            {"propertyId": "current_temperature", "mode": "read"},
            {"propertyId": "eco_temperature", "mode": "readwrite"},
            {"propertyId": "comfort_temperature", "mode": "readwrite"},
        ],
    }
    mock_appartme_api.get_device_properties.return_value = {
        "values": [
            {"propertyId": "thermostat_mode", "value": "eco", "mode": "readwrite"},
            {"propertyId": "current_temperature", "value": 22.5, "mode": "read"},
            {"propertyId": "eco_temperature", "value": 18.0, "mode": "readwrite"},
            {"propertyId": "comfort_temperature", "value": 24.0, "mode": "readwrite"},
        ]
    }

    async def mock_set_device_property_value(device_id, property_id, value):
        for prop in mock_appartme_api.get_device_properties.return_value["values"]:
            if prop["propertyId"] == property_id:
                prop["value"] = value

    mock_appartme_api.set_device_property_value.side_effect = (
        mock_set_device_property_value
    )

    with patch(
        "homeassistant.components.appartme.AppartmeCloudAPI",
        return_value=mock_appartme_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    climate_entity_id = "climate.main_module_heating"

    # Verify initial state
    state = hass.states.get(climate_entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == HVACMode.HEAT
    assert state.attributes["preset_mode"] == PRESET_ECO
    assert state.attributes["current_temperature"] == 22.5
    assert state.attributes["temperature"] == 18.0

    # Test setting preset mode to comfort
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": climate_entity_id, "preset_mode": PRESET_COMFORT},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify the preset mode changed
    state = hass.states.get(climate_entity_id)
    assert state.attributes["preset_mode"] == PRESET_COMFORT

    # Test setting target temperature
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": climate_entity_id, ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify the target temperature changed
    state = hass.states.get(climate_entity_id)
    assert state.attributes["temperature"] == 23.0
