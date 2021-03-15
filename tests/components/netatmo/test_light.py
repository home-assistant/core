"""The tests for Netatmo device triggers."""
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_WEBHOOK_ID
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .common import simulate_webhook


async def test_light_setup_and_services(hass, light_entry):
    """Test setup and services."""
    webhook_id = light_entry.data[CONF_WEBHOOK_ID]

    assert (
        hass.data["netatmo"][light_entry.entry_id]["netatmo_data_handler"].webhook
        is False
    )

    # Fake webhook activation
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

    # Trigger light mode change
    response = (
        b'{"user_id": "91763b24c43d3e344f424e8d","event_type": "light_mode",'
        b'"device_id": "12:34:56:00:a5:a4","home_id": "91763b24c43d3e344f424e8b",'
        b'"home_name": "MYHOME","camera_id": "12:34:56:00:a5:a4",'
        b'"event_id": "601dce1560abca1ebad9b723","push_type": "NOC-light_mode","sub_type": "on"}'
    )
    await simulate_webhook(hass, webhook_id, response)

    assert hass.states.get(light_entity).state == "on"

    # Trigger light mode change with erroneous webhook data
    response = (
        b'{"user_id": "91763b24c43d3e344f424e8d","event_type": "light_mode",'
        b'"device_id": "12:34:56:00:a5:a4","home_id": "91763b24c43d3e344f424e8b",'
        b'"home_name": "MYHOME"}'
    )
    await simulate_webhook(hass, webhook_id, response)

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
