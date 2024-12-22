"""Test Qbus switch entities."""

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .common import PAYLOAD_CONFIG, TOPIC_CONFIG

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient

_PAYLOAD_SWITCH_STATE_ON = '{"id":"UL10","properties":{"value":true},"type":"state"}'
_PAYLOAD_SWITCH_STATE_OFF = '{"id":"UL10","properties":{"value":false},"type":"state"}'

_TOPIC_SWITCH_STATE = "cloudapp/QBUSMQTTGW/UL1/UL10/state"

_SWITCH_ENTITY_ID = "switch.qbus_000001_10"


async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn on and off."""

    # Setup entry
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire config payload
    async_fire_mqtt_message(hass, TOPIC_CONFIG, PAYLOAD_CONFIG)
    await hass.async_block_till_done()

    # Switch ON
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _SWITCH_ENTITY_ID},
        blocking=True,
    )

    # Test MQTT publish
    assert len(mqtt_mock.async_publish.mock_calls) == 1

    # Simulate response
    async_fire_mqtt_message(hass, _TOPIC_SWITCH_STATE, _PAYLOAD_SWITCH_STATE_ON)
    await hass.async_block_till_done()

    # Test ON
    assert hass.states.get(_SWITCH_ENTITY_ID).state == STATE_ON

    # Switch OFF
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _SWITCH_ENTITY_ID},
        blocking=True,
    )

    # Test MQTT publish
    assert len(mqtt_mock.async_publish.mock_calls) == 1

    # Simulate response
    async_fire_mqtt_message(hass, _TOPIC_SWITCH_STATE, _PAYLOAD_SWITCH_STATE_OFF)
    await hass.async_block_till_done()

    # Test OFF
    assert hass.states.get(_SWITCH_ENTITY_ID).state == STATE_OFF
