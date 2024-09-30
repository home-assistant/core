"""Tests for the Appartme light platform."""

from unittest.mock import patch

from homeassistant.components.appartme.const import DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON

from tests.common import MockConfigEntry


async def test_light_entity(hass, mock_appartme_api):
    """Test the Appartme light entity."""
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
        "properties": [{"propertyId": "lighting", "mode": "readwrite"}],
    }
    mock_appartme_api.get_device_properties.return_value = {
        "values": [{"propertyId": "lighting", "value": False, "mode": "readwrite"}]
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

    light_entity_id = "light.main_module_lighting"

    # Verify initial state
    entity = hass.states.get(light_entity_id)
    assert entity is not None
    assert entity.state == STATE_OFF

    # Turn on the light
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": light_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify the light is on
    state = hass.states.get(light_entity_id)
    assert state.state == STATE_ON
