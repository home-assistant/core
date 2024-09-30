"""Tests for the Appartme valve platform."""

from unittest.mock import patch

from homeassistant.components.appartme.const import DOMAIN
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN

from tests.common import MockConfigEntry


async def test_valve_entity(hass, mock_appartme_api):
    """Test the Appartme water valve entity."""
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
        "properties": [{"propertyId": "water", "mode": "readwrite"}],
    }
    mock_appartme_api.get_device_properties.return_value = {
        "values": [{"propertyId": "water", "value": False, "mode": "readwrite"}]
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
        # Set up the integration (this will set up the 'valve' platform automatically)
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        assert result  # Ensure setup was successful
        await hass.async_block_till_done()

    valve_entity_id = "valve.main_module_water"

    # Verify the entity exists
    state = hass.states.get(valve_entity_id)
    assert state is not None, f"Entity {valve_entity_id} not found"

    # Verify initial state
    assert state.state == "closed"

    # Open the valve
    await hass.services.async_call(
        VALVE_DOMAIN,
        "open_valve",
        {"entity_id": valve_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify the valve is open
    state = hass.states.get(valve_entity_id)
    assert state.state == "open"
