"""Test Senziio binary sensor entities."""

from unittest.mock import patch

from homeassistant.components.senziio.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import assert_entity_state_is, when_message_received_is

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient

MOTION_ENTITY = "binary_sensor.motion"
PRESENCE_ENTITY = "binary_sensor.presence"


async def test_loading_binary_sensor_entities(
    hass: HomeAssistant, config_entry: MockConfigEntry, mqtt_mock: MqttMockHAClient
):
    """Test creation of binary sensor entities."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.mqtt.async_wait_for_mqtt_client",
        return_value=True,
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert config_entry.state == ConfigEntryState.LOADED

    # initial entity states should be unknown
    assert_entity_state_is(hass, MOTION_ENTITY, STATE_UNKNOWN)
    assert_entity_state_is(hass, PRESENCE_ENTITY, STATE_UNKNOWN)

    senziio_device = hass.data[DOMAIN][config_entry.entry_id]
    topic_motion = senziio_device.entity_topic("motion")
    topic_presence = senziio_device.entity_topic("presence")

    await when_message_received_is(hass, topic_motion, '{"motion": true}')
    assert_entity_state_is(hass, MOTION_ENTITY, STATE_ON)

    await when_message_received_is(hass, topic_motion, '{"motion": false}')
    assert_entity_state_is(hass, MOTION_ENTITY, STATE_OFF)

    await when_message_received_is(hass, topic_presence, '{"presence": true}')
    assert_entity_state_is(hass, PRESENCE_ENTITY, STATE_ON)

    await when_message_received_is(hass, topic_presence, '{"presence": false}')
    assert_entity_state_is(hass, PRESENCE_ENTITY, STATE_OFF)
