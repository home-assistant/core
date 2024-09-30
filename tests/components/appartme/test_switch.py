"""Tests for the Appartme switch platform."""

from unittest.mock import patch

from homeassistant.components.appartme.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON

from tests.common import MockConfigEntry


async def test_switch_entities(hass, mock_appartme_api):
    """Test the Appartme switch entities."""
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
            {"propertyId": "sockets", "mode": "readwrite"},
            {"propertyId": "fifth_channel", "mode": "readwrite"},
        ],
    }
    mock_appartme_api.get_device_properties.return_value = {
        "values": [
            {"propertyId": "sockets", "value": False, "mode": "readwrite"},
            {"propertyId": "fifth_channel", "value": True, "mode": "readwrite"},
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

    sockets_entity_id = "switch.main_module_sockets"
    fifth_channel_entity_id = "switch.main_module_additional_channel"

    # Test 'sockets' switch
    sockets_switch = hass.states.get(sockets_entity_id)
    assert sockets_switch.state == STATE_OFF

    # Turn on the 'sockets' switch
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": sockets_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    sockets_switch = hass.states.get(sockets_entity_id)
    assert sockets_switch.state == STATE_ON

    # Test 'fifth_channel' switch
    fifth_channel_switch = hass.states.get(fifth_channel_entity_id)
    assert fifth_channel_switch.state == STATE_ON

    # Turn off the 'fifth_channel' switch
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": fifth_channel_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    fifth_channel_switch = hass.states.get(fifth_channel_entity_id)
    assert fifth_channel_switch.state == STATE_OFF
