"""The tests for the  MQTT binary sensor platform."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components import binary_sensor, mqtt
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .test_common import (
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_discovery_update_unchanged,
    help_test_encoding_subscribable_topics,
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_reload_with_config,
    help_test_reloadable,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setup_manual_entity_from_yaml,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import (
    async_fire_mqtt_message,
    async_fire_time_changed,
    mock_restore_cache,
)
from tests.typing import MqttMockHAClientGenerator

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        binary_sensor.DOMAIN: {
            "name": "test",
            "state_topic": "test-topic",
        }
    }
}


@pytest.fixture(autouse=True)
def binary_sensor_platform_only():
    """Only setup the binary_sensor platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


async def test_setting_sensor_value_expires_availability_topic(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the expiration of the value."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "expire_after": 4,
                    "force_update": True,
                    "availability_topic": "availability-topic",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")

    # State should be unavailable since expire_after is defined and > 0
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE

    await expires_helper(hass)


async def test_setting_sensor_value_expires(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the expiration of the value."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "expire_after": 4,
                    "force_update": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    # State should be unavailable since expire_after is defined and > 0
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE

    await expires_helper(hass)


async def expires_helper(hass: HomeAssistant) -> None:
    """Run the basic expiry code."""
    realnow = dt_util.utcnow()
    now = datetime(realnow.year + 1, 1, 1, 1, tzinfo=dt_util.UTC)
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(hass, "test-topic", "ON")
        await hass.async_block_till_done()

    # Value was set correctly.
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    # Time jump +3s
    now = now + timedelta(seconds=3)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is not yet expired
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    # Next message resets timer
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(hass, "test-topic", "OFF")
        await hass.async_block_till_done()

    # Value was updated correctly.
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF

    # Time jump +3s
    now = now + timedelta(seconds=3)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is not yet expired
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF

    # Time jump +2s
    now = now + timedelta(seconds=2)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is expired now
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE


async def test_expiration_on_discovery_and_discovery_update_of_binary_sensor(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that binary_sensor with expire_after set behaves correctly on discovery and discovery update."""
    await mqtt_mock_entry_no_yaml_config()
    config = {
        "name": "Test",
        "state_topic": "test-topic",
        "expire_after": 4,
        "force_update": True,
    }

    config_msg = json.dumps(config)

    # Set time and publish config message to create binary_sensor via discovery with 4 s expiry
    realnow = dt_util.utcnow()
    now = datetime(realnow.year + 1, 1, 1, 1, tzinfo=dt_util.UTC)
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(
            hass, "homeassistant/binary_sensor/bla/config", config_msg
        )
        await hass.async_block_till_done()

    # Test that binary_sensor is not available
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE

    # Publish state message
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_mqtt_message(hass, "test-topic", "ON")
        await hass.async_block_till_done()

    # Test that binary_sensor has correct state
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    # Advance +3 seconds
    now = now + timedelta(seconds=3)
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

    # binary_sensor is not yet expired
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    # Resend config message to update discovery
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(
            hass, "homeassistant/binary_sensor/bla/config", config_msg
        )
        await hass.async_block_till_done()

    # Test that binary_sensor has not expired
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    # Add +2 seconds
    now = now + timedelta(seconds=2)
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

    # Test that binary_sensor has expired
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE

    # Resend config message to update discovery
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_mqtt_message(
            hass, "homeassistant/binary_sensor/bla/config", config_msg
        )
        await hass.async_block_till_done()

    # Test that binary_sensor is still expired
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE


async def test_setting_sensor_value_via_mqtt_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("binary_sensor.test")

    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "ON")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "test-topic", "OFF")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test-topic", "None")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNKNOWN


async def test_invalid_sensor_value_via_mqtt_message(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("binary_sensor.test")

    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "0N")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNKNOWN
    assert "No matching payload found for entity" in caplog.text
    caplog.clear()
    assert "No matching payload found for entity" not in caplog.text

    async_fire_mqtt_message(hass, "test-topic", "ON")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "test-topic", "0FF")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON
    assert "No matching payload found for entity" in caplog.text


async def test_setting_sensor_value_via_mqtt_message_and_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "value_template": '{%if is_state(entity_id,"on")-%}OFF'
                    "{%-else-%}ON{%-endif%}",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "test-topic", "")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF


async def test_setting_sensor_value_via_mqtt_message_and_template2(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "value_template": "{{value | upper}}",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "on")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "test-topic", "off")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test-topic", "illegal")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF
    assert "template output: 'ILLEGAL'" in caplog.text


async def test_setting_sensor_value_via_mqtt_message_and_template_and_raw_state_encoding(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test processing a raw value via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "encoding": "",
                    "state_topic": "test-topic",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "value_template": "{%if value|unpack('b')-%}ON{%else%}OFF{%-endif-%}",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", b"\x01")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "test-topic", b"\x00")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF


async def test_setting_sensor_value_via_mqtt_message_empty_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "value_template": '{%if value == "ABC"%}ON{%endif%}',
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "DEF")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "ABC")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON


async def test_valid_device_class(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of a valid sensor class."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "device_class": "motion",
                    "state_topic": "test-topic",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("binary_sensor.test")
    assert state.attributes.get("device_class") == "motion"


async def test_invalid_device_class(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the setting of an invalid sensor class."""
    assert not await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "device_class": "abc123",
                    "state_topic": "test-topic",
                }
            }
        },
    )
    assert "Invalid config for [mqtt]: expected BinarySensorDeviceClass" in caplog.text


async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass,
        mqtt_mock_entry_with_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass,
        mqtt_mock_entry_with_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass,
        mqtt_mock_entry_with_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass,
        mqtt_mock_entry_with_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_force_update_disabled(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test force update option."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    events = []

    @callback
    def test_callback(event) -> None:
        """Verify event got called."""
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, test_callback)

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_force_update_enabled(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test force update option."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "force_update": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    events = []

    @callback
    def test_callback(event) -> None:
        """Verify event got called."""
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, test_callback)

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    assert len(events) == 2


async def test_off_delay(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test off_delay option."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                binary_sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "off_delay": 30,
                    "force_update": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    events = []

    @callback
    def test_callback(event) -> None:
        """Verify event got called."""
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, test_callback)

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON
    assert len(events) == 2

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF
    assert len(events) == 3


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_with_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass,
        mqtt_mock_entry_with_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one sensor per unique_id."""
    config = {
        mqtt.DOMAIN: {
            binary_sensor.DOMAIN: [
                {
                    "name": "Test 1",
                    "state_topic": "test-topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
                {
                    "name": "Test 2",
                    "state_topic": "test-topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
            ]
        }
    }
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, binary_sensor.DOMAIN, config
    )


async def test_discovery_removal_binary_sensor(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered binary_sensor."""
    data = json.dumps(DEFAULT_CONFIG[mqtt.DOMAIN][binary_sensor.DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, binary_sensor.DOMAIN, data
    )


async def test_discovery_update_binary_sensor_topic_template(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered binary_sensor."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][binary_sensor.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][binary_sensor.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "sensor/state1"
    config2["state_topic"] = "sensor/state2"
    config1["value_template"] = "{{ value_json.state1.state }}"
    config2["value_template"] = "{{ value_json.state2.state }}"

    state_data1 = [
        ([("sensor/state1", '{"state1":{"state":"ON"}}')], "on", None),
    ]
    state_data2 = [
        ([("sensor/state2", '{"state2":{"state":"OFF"}}')], "off", None),
        ([("sensor/state2", '{"state2":{"state":"ON"}}')], "on", None),
        ([("sensor/state1", '{"state1":{"state":"OFF"}}')], "on", None),
        ([("sensor/state1", '{"state2":{"state":"OFF"}}')], "on", None),
        ([("sensor/state2", '{"state1":{"state":"OFF"}}')], "on", None),
        ([("sensor/state2", '{"state2":{"state":"OFF"}}')], "off", None),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        binary_sensor.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_discovery_update_binary_sensor_template(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered binary_sensor."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][binary_sensor.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][binary_sensor.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "sensor/state1"
    config2["state_topic"] = "sensor/state1"
    config1["value_template"] = "{{ value_json.state1.state }}"
    config2["value_template"] = "{{ value_json.state2.state }}"

    state_data1 = [
        ([("sensor/state1", '{"state1":{"state":"ON"}}')], "on", None),
    ]
    state_data2 = [
        ([("sensor/state1", '{"state2":{"state":"OFF"}}')], "off", None),
        ([("sensor/state1", '{"state2":{"state":"ON"}}')], "on", None),
        ([("sensor/state1", '{"state1":{"state":"OFF"}}')], "on", None),
        ([("sensor/state1", '{"state2":{"state":"OFF"}}')], "off", None),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        binary_sensor.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("json_attributes_topic", '{ "id": 123 }', "id", 123),
        (
            "json_attributes_topic",
            '{ "id": 123, "temperature": 34.0 }',
            "temperature",
            34.0,
        ),
        ("state_topic", "ON", None, "on"),
    ],
)
async def test_encoding_subscribable_topics(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    topic,
    value,
    attribute,
    attribute_value,
) -> None:
    """Test handling of incoming encoded payload."""
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][binary_sensor.DOMAIN],
        topic,
        value,
        attribute,
        attribute_value,
    )


async def test_discovery_update_unchanged_binary_sensor(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered binary_sensor."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][binary_sensor.DOMAIN])
    config1["name"] = "Beer"

    data1 = json.dumps(config1)
    with patch(
        "homeassistant.components.mqtt.binary_sensor.MqttBinarySensor.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            binary_sensor.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer",' '  "off_delay": -1 }'
    data2 = '{ "name": "Milk",' '  "state_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        binary_sensor.DOMAIN,
        data1,
        data2,
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT binary sensor device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass,
        mqtt_mock_entry_no_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT binary sensor device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass,
        mqtt_mock_entry_no_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass,
        mqtt_mock_entry_no_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass,
        mqtt_mock_entry_with_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        binary_sensor.DOMAIN,
        DEFAULT_CONFIG,
        None,
    )


async def test_reloadable(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Test reloading the MQTT platform."""
    domain = binary_sensor.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


@pytest.mark.parametrize(
    ("payload1", "state1", "payload2", "state2"),
    [("ON", "on", "OFF", "off"), ("OFF", "off", "ON", "on")],
)
async def test_cleanup_triggers_and_restoring_state(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    freezer,
    payload1,
    state1,
    payload2,
    state2,
) -> None:
    """Test cleanup old triggers at reloading and restoring the state."""
    domain = binary_sensor.DOMAIN
    config1 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][domain])
    config1["name"] = "test1"
    config1["expire_after"] = 30
    config1["state_topic"] = "test-topic1"
    config2 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][domain])
    config2["name"] = "test2"
    config2["expire_after"] = 5
    config2["state_topic"] = "test-topic2"

    freezer.move_to("2022-02-02 12:01:00+01:00")

    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {mqtt.DOMAIN: {binary_sensor.DOMAIN: [config1, config2]}},
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "test-topic1", payload1)
    state = hass.states.get("binary_sensor.test1")
    assert state.state == state1

    async_fire_mqtt_message(hass, "test-topic2", payload1)
    state = hass.states.get("binary_sensor.test2")
    assert state.state == state1

    freezer.move_to("2022-02-02 12:01:10+01:00")

    await help_test_reload_with_config(
        hass, caplog, tmp_path, {mqtt.DOMAIN: {domain: [config1, config2]}}
    )

    state = hass.states.get("binary_sensor.test1")
    assert state.state == state1

    state = hass.states.get("binary_sensor.test2")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "test-topic1", payload2)
    state = hass.states.get("binary_sensor.test1")
    assert state.state == state2

    async_fire_mqtt_message(hass, "test-topic2", payload2)
    state = hass.states.get("binary_sensor.test2")
    assert state.state == state2


async def test_skip_restoring_state_with_over_due_expire_trigger(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    freezer,
) -> None:
    """Test restoring a state with over due expire timer."""

    freezer.move_to("2022-02-02 12:02:00+01:00")
    domain = binary_sensor.DOMAIN
    config3 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][domain])
    config3["name"] = "test3"
    config3["expire_after"] = 10
    config3["state_topic"] = "test-topic3"
    fake_state = State(
        "binary_sensor.test3",
        "on",
        {},
        last_changed=datetime.fromisoformat("2022-02-02 12:01:35+01:00"),
    )
    mock_restore_cache(hass, (fake_state,))

    assert await async_setup_component(
        hass, mqtt.DOMAIN, {mqtt.DOMAIN: {domain: config3}}
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()
    state = hass.states.get("binary_sensor.test3")
    assert state.state == STATE_UNAVAILABLE


async def test_setup_manual_entity_from_yaml(hass: HomeAssistant) -> None:
    """Test setup manual configured MQTT entity."""
    platform = binary_sensor.DOMAIN
    await help_test_setup_manual_entity_from_yaml(hass, DEFAULT_CONFIG)
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    tmp_path: Path,
) -> None:
    """Test unloading the config entry."""
    domain = binary_sensor.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry_with_yaml_config, tmp_path, domain, config
    )
