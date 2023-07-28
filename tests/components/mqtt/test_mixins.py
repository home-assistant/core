"""The tests for shared code of the MQTT platform."""

from unittest.mock import patch

import pytest

from homeassistant.components import mqtt, sensor
from homeassistant.components.mqtt.sensor import DEFAULT_NAME as DEFAULT_SENSOR_NAME
from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
)

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


@pytest.mark.parametrize(
    ("hass_config", "entity_id", "friendly_name", "device_name", "assert_log"),
    [
        (  # default_entity_name_without_device_name
            {
                mqtt.DOMAIN: {
                    sensor.DOMAIN: {
                        "state_topic": "test-topic",
                        "unique_id": "veryunique",
                        "device": {"identifiers": ["helloworld"]},
                    }
                }
            },
            "sensor.none_mqtt_sensor",
            DEFAULT_SENSOR_NAME,
            None,
            True,
        ),
        (  # default_entity_name_with_device_name
            {
                mqtt.DOMAIN: {
                    sensor.DOMAIN: {
                        "state_topic": "test-topic",
                        "unique_id": "veryunique",
                        "device": {"name": "Test", "identifiers": ["helloworld"]},
                    }
                }
            },
            "sensor.test_mqtt_sensor",
            "Test MQTT Sensor",
            "Test",
            False,
        ),
        (  # name_follows_device_class
            {
                mqtt.DOMAIN: {
                    sensor.DOMAIN: {
                        "state_topic": "test-topic",
                        "unique_id": "veryunique",
                        "device_class": "humidity",
                        "device": {"name": "Test", "identifiers": ["helloworld"]},
                    }
                }
            },
            "sensor.test_humidity",
            "Test Humidity",
            "Test",
            False,
        ),
        (  # name_follows_device_class_without_device_name
            {
                mqtt.DOMAIN: {
                    sensor.DOMAIN: {
                        "state_topic": "test-topic",
                        "unique_id": "veryunique",
                        "device_class": "humidity",
                        "device": {"identifiers": ["helloworld"]},
                    }
                }
            },
            "sensor.none_humidity",
            "Humidity",
            None,
            True,
        ),
        (  # name_overrides_device_class
            {
                mqtt.DOMAIN: {
                    sensor.DOMAIN: {
                        "name": "MySensor",
                        "state_topic": "test-topic",
                        "unique_id": "veryunique",
                        "device_class": "humidity",
                        "device": {"name": "Test", "identifiers": ["helloworld"]},
                    }
                }
            },
            "sensor.test_mysensor",
            "Test MySensor",
            "Test",
            False,
        ),
        (  # name_set_no_device_name_set
            {
                mqtt.DOMAIN: {
                    sensor.DOMAIN: {
                        "name": "MySensor",
                        "state_topic": "test-topic",
                        "unique_id": "veryunique",
                        "device_class": "humidity",
                        "device": {"identifiers": ["helloworld"]},
                    }
                }
            },
            "sensor.none_mysensor",
            "MySensor",
            None,
            True,
        ),
        (  # none_entity_name_with_device_name
            {
                mqtt.DOMAIN: {
                    sensor.DOMAIN: {
                        "name": None,
                        "state_topic": "test-topic",
                        "unique_id": "veryunique",
                        "device_class": "humidity",
                        "device": {"name": "Test", "identifiers": ["helloworld"]},
                    }
                }
            },
            "sensor.test",
            "Test",
            "Test",
            False,
        ),
        (  # none_entity_name_without_device_name
            {
                mqtt.DOMAIN: {
                    sensor.DOMAIN: {
                        "name": None,
                        "state_topic": "test-topic",
                        "unique_id": "veryunique",
                        "device_class": "humidity",
                        "device": {"identifiers": ["helloworld"]},
                    }
                }
            },
            "sensor.mqtt_veryunique",
            "mqtt veryunique",
            None,
            True,
        ),
        (  # entity_name_and_device_name_the_sane
            {
                mqtt.DOMAIN: {
                    sensor.DOMAIN: {
                        "name": "Hello world",
                        "state_topic": "test-topic",
                        "unique_id": "veryunique",
                        "device_class": "humidity",
                        "device": {
                            "identifiers": ["helloworld"],
                            "name": "Hello world",
                        },
                    }
                }
            },
            "sensor.hello_world",
            "Hello world",
            "Hello world",
            False,
        ),
    ],
    ids=[
        "default_entity_name_without_device_name",
        "default_entity_name_with_device_name",
        "name_follows_device_class",
        "name_follows_device_class_without_device_name",
        "name_overrides_device_class",
        "name_set_no_device_name_set",
        "none_entity_name_with_device_name",
        "none_entity_name_without_device_name",
        "entity_name_and_device_name_the_sane",
    ],
)
@patch("homeassistant.components.mqtt.PLATFORMS", [Platform.SENSOR])
async def test_default_entity_and_device_name(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    entity_id: str,
    friendly_name: str,
    device_name: str | None,
    assert_log: bool,
) -> None:
    """Test device name setup with and without a device_class set.

    This is a test helper for the _setup_common_attributes_from_config mixin.
    """
    await mqtt_mock_entry()

    registry = dr.async_get(hass)

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.name == device_name

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == friendly_name

    assert (
        "MQTT device information always needs to include a name" in caplog.text
    ) is assert_log
