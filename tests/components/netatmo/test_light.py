"""The tests for Netatmo device triggers."""
from freezegun import freeze_time

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers.dispatcher import async_dispatcher_send


@freeze_time("2019-06-16")
async def test_setup_component_with_webhook(hass, light_entry):
    """Test ."""
    await hass.async_block_till_done()

    assert (
        hass.data["netatmo"][light_entry.entry_id]["netatmo_data_handler"].webhook
        is False
    )

    webhook_data = {
        "user_id": "123",
        "user": {"id": "123", "email": "foo@bar.com"},
        "push_type": "webhook_activation",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-None",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()
    assert (
        hass.data["netatmo"][light_entry.entry_id]["netatmo_data_handler"].webhook
        is True
    )

    light_entity = "light.netatmo_garden"
    assert hass.states.get(light_entity).state == "unavailable"

    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8d",
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
        "home_id": "91763b24c43d3e344f424e8b",
        "home_name": "MYHOME",
        "camera_id": "12:34:56:00:a5:a4",
        "event_id": "601dce1560abca1ebad9b723",
        "push_type": "NOC-light_mode",
        "sub_type": "on",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-light_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    assert hass.states.get(light_entity).state == "on"

    # Trigger
    webhook_data = {
        "user_id": "91763b24c43d3e344f424e8d",
        "event_type": "light_mode",
        "device_id": "12:34:56:00:a5:a4",
        "home_id": "91763b24c43d3e344f424e8b",
        "home_name": "MYHOME",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-light_mode",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    # Test turning light off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: light_entity},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test turning light on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: light_entity},
        blocking=True,
    )
    await hass.async_block_till_done()
