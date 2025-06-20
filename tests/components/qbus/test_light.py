"""Test Qbus light entities."""

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient

# 186 = 73% (rounded)
_BRIGHTNESS = 186
_BRIGHTNESS_PCT = 73

_PAYLOAD_LIGHT_STATE_ON = '{"id":"UL15","properties":{"value":60},"type":"state"}'
_PAYLOAD_LIGHT_STATE_BRIGHTNESS = (
    '{"id":"UL15","properties":{"value":' + str(_BRIGHTNESS_PCT) + '},"type":"state"}'
)
_PAYLOAD_LIGHT_STATE_OFF = '{"id":"UL15","properties":{"value":0},"type":"state"}'

_PAYLOAD_LIGHT_SET_STATE_ON = '{"id": "UL15", "type": "action", "action": "on"}'
_PAYLOAD_LIGHT_SET_STATE_BRIGHTNESS = (
    '{"id": "UL15", "type": "state", "properties": {"value": '
    + str(_BRIGHTNESS_PCT)
    + "}}"
)
_PAYLOAD_LIGHT_SET_STATE_OFF = '{"id": "UL15", "type": "action", "action": "off"}'

_TOPIC_LIGHT_STATE = "cloudapp/QBUSMQTTGW/UL1/UL15/state"
_TOPIC_LIGHT_SET_STATE = "cloudapp/QBUSMQTTGW/UL1/UL15/setState"

_LIGHT_ENTITY_ID = "light.media_room"


async def test_light(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test turning on and off."""

    # Switch ON
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY_ID},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        _TOPIC_LIGHT_SET_STATE, _PAYLOAD_LIGHT_SET_STATE_ON, 0, False
    )

    # Simulate response
    async_fire_mqtt_message(hass, _TOPIC_LIGHT_STATE, _PAYLOAD_LIGHT_STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY_ID).state == STATE_ON

    # Set brightness
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: _LIGHT_ENTITY_ID,
            ATTR_BRIGHTNESS: _BRIGHTNESS,
        },
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        _TOPIC_LIGHT_SET_STATE, _PAYLOAD_LIGHT_SET_STATE_BRIGHTNESS, 0, False
    )

    # Simulate response
    async_fire_mqtt_message(hass, _TOPIC_LIGHT_STATE, _PAYLOAD_LIGHT_STATE_BRIGHTNESS)
    await hass.async_block_till_done()

    entity = hass.states.get(_LIGHT_ENTITY_ID)
    assert entity.state == STATE_ON
    assert entity.attributes.get(ATTR_BRIGHTNESS) == _BRIGHTNESS

    # Switch OFF
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY_ID},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        _TOPIC_LIGHT_SET_STATE, _PAYLOAD_LIGHT_SET_STATE_OFF, 0, False
    )

    # Simulate response
    async_fire_mqtt_message(hass, _TOPIC_LIGHT_STATE, _PAYLOAD_LIGHT_STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY_ID).state == STATE_OFF
