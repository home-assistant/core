"""Test Qbus scene entities."""

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient

_PAYLOAD_SCENE_STATE = '{"id":"UL25","properties":{"value":true},"type":"state"}'
_PAYLOAD_SCENE_ACTIVATE = '{"id": "UL25", "type": "action", "action": "active"}'

_TOPIC_SCENE_STATE = "cloudapp/QBUSMQTTGW/UL1/UL25/state"
_TOPIC_SCENE_SET_STATE = "cloudapp/QBUSMQTTGW/UL1/UL25/setState"

_SCENE_ENTITY_ID = "scene.ctd_000001_watching_tv"


async def test_scene(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test scene."""

    assert hass.states.get(_SCENE_ENTITY_ID).state == STATE_UNKNOWN

    # Activate scene
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _SCENE_ENTITY_ID},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        _TOPIC_SCENE_SET_STATE, _PAYLOAD_SCENE_ACTIVATE, 0, False
    )

    # Simulate response
    async_fire_mqtt_message(hass, _TOPIC_SCENE_STATE, _PAYLOAD_SCENE_STATE)
    await hass.async_block_till_done()

    assert hass.states.get(_SCENE_ENTITY_ID).state != STATE_UNKNOWN
