"""The tests for shared code of the MQTT platform."""

from unittest.mock import patch

import pytest

from homeassistant.components import mqtt, sensor
from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import HomeAssistant, callback

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "availability_topic": "test-topic",
                    "payload_available": True,
                    "payload_not_available": False,
                    "value_template": "{{ int(value) or '' }}",
                    "availability_template": "{{ value != '0' }}",
                }
            }
        }
    ],
)
@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.SENSOR])
async def test_availability_with_shared_state_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test the state is not changed twice.

    When an entity with a shared state_topic and availability_topic becomes available
    The state should only change once.
    """
    await mqtt_mock_entry()

    events = []

    @callback
    def test_callback(event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, test_callback)

    async_fire_mqtt_message(hass, "test-topic", "100")
    await hass.async_block_till_done()
    # Initially the state and the availability change
    assert len(events) == 1

    events.clear()
    async_fire_mqtt_message(hass, "test-topic", "50")
    await hass.async_block_till_done()
    assert len(events) == 1

    events.clear()
    async_fire_mqtt_message(hass, "test-topic", "0")
    await hass.async_block_till_done()
    # Only the availability is changed since the template resukts in an empty payload
    # This does not change the state
    assert len(events) == 1

    events.clear()
    async_fire_mqtt_message(hass, "test-topic", "10")
    await hass.async_block_till_done()
    # The availability is changed but the topic is shared,
    # hence there the state will be written when the value is updated
    assert len(events) == 1
