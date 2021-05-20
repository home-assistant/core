"""The tests for Netatmo light."""
from unittest.mock import patch

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_WEBHOOK_ID

from .common import FAKE_WEBHOOK_ACTIVATION, simulate_webhook


async def test_light_setup_and_services(hass, light_entry):
    """Test setup and services."""
    webhook_id = light_entry.data[CONF_WEBHOOK_ID]

    # Fake webhook activation
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    light_entity = "light.netatmo_garden"
    assert hass.states.get(light_entity).state == "unavailable"

    # Trigger light mode change
    response = {
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
        "camera_id": "12:34:56:00:a5:a4",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NOC-light_mode",
        "sub_type": "on",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(light_entity).state == "on"

    # Trigger light mode change with erroneous webhook data
    response = {
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
    }
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(light_entity).state == "on"

    # Test turning light off
    with patch("pyatmo.camera.CameraData.set_state") as mock_set_state:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: light_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            home_id="91763b24c43d3e344f424e8b",
            camera_id="12:34:56:00:a5:a4",
            floodlight="auto",
        )

    # Test turning light on
    with patch("pyatmo.camera.CameraData.set_state") as mock_set_state:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: light_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            home_id="91763b24c43d3e344f424e8b",
            camera_id="12:34:56:00:a5:a4",
            floodlight="on",
        )
