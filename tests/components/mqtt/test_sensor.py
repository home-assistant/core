"""The tests for the MQTT sensor platform."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import mqtt, sensor
from homeassistant.components.mqtt.sensor import MQTT_SENSOR_ATTRIBUTES_BLOCKED
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .test_common import (
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_list_payload,
    help_test_default_availability_list_payload_all,
    help_test_default_availability_list_payload_any,
    help_test_default_availability_list_single,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_discovery_update_availability,
    help_test_discovery_update_unchanged,
    help_test_encoding_subscribable_topics,
    help_test_entity_category,
    help_test_entity_debug_info,
    help_test_entity_debug_info_max_messages,
    help_test_entity_debug_info_message,
    help_test_entity_debug_info_remove,
    help_test_entity_debug_info_update_entity_id,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_disabled_by_default,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_reload_with_config,
    help_test_reloadable,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_setup_manual_entity_from_yaml,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import (
    async_fire_mqtt_message,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)
from tests.typing import MqttMockHAClientGenerator

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {sensor.DOMAIN: {"name": "test", "state_topic": "test-topic"}}
}


@pytest.fixture(autouse=True)
def sensor_platform_only():
    """Only setup the sensor platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.SENSOR]):
        yield


async def test_setting_sensor_value_via_mqtt_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "unit_of_measurement": "fav unit",
                    "suggested_display_precision": 1,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "test-topic", "100.22")
    state = hass.states.get("sensor.test")

    # Rounding happens at the frontend
    # the state should show the received value
    assert state.state == "100.22"
    assert state.attributes.get("unit_of_measurement") == "fav unit"


@pytest.mark.parametrize(
    ("device_class", "native_value", "state_value", "log"),
    [
        (sensor.SensorDeviceClass.DATE, "2021-11-18", "2021-11-18", False),
        (sensor.SensorDeviceClass.DATE, "invalid", STATE_UNKNOWN, True),
        (
            sensor.SensorDeviceClass.TIMESTAMP,
            "2021-11-18T20:25:00+00:00",
            "2021-11-18T20:25:00+00:00",
            False,
        ),
        (
            sensor.SensorDeviceClass.TIMESTAMP,
            "2021-11-18 20:25:00+00:00",
            "2021-11-18T20:25:00+00:00",
            False,
        ),
        (
            sensor.SensorDeviceClass.TIMESTAMP,
            "2021-11-18 20:25:00+01:00",
            "2021-11-18T19:25:00+00:00",
            False,
        ),
        (
            sensor.SensorDeviceClass.TIMESTAMP,
            "2021-13-18T35:25:00+00:00",
            STATE_UNKNOWN,
            True,
        ),
        (sensor.SensorDeviceClass.TIMESTAMP, "invalid", STATE_UNKNOWN, True),
    ],
)
async def test_setting_sensor_native_value_handling_via_mqtt_message(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    device_class,
    native_value,
    state_value,
    log,
) -> None:
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "device_class": device_class,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "test-topic", native_value)
    state = hass.states.get("sensor.test")

    assert state.state == state_value
    assert state.attributes.get("device_class") == device_class
    assert log == ("Invalid state message" in caplog.text)


async def test_setting_numeric_sensor_native_value_handling_via_mqtt_message(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
) -> None:
    """Test the setting of a numeric sensor value via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "value_template": "{{ value_json.power }}",
                    "device_class": "power",
                    "unit_of_measurement": "W",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    # float value
    async_fire_mqtt_message(hass, "test-topic", '{ "power": 45.3, "current": 5.24 }')
    state = hass.states.get("sensor.test")
    assert state.attributes.get("device_class") == "power"
    assert state.state == "45.3"

    # null value, native value should be None
    async_fire_mqtt_message(hass, "test-topic", '{ "power": null, "current": 5.34 }')
    state = hass.states.get("sensor.test")
    assert state.state == "unknown"

    # int value
    async_fire_mqtt_message(hass, "test-topic", '{ "power": 20, "current": 5.34 }')
    state = hass.states.get("sensor.test")
    assert state.state == "20"

    # int value
    async_fire_mqtt_message(hass, "test-topic", '{ "power": "21", "current": 5.34 }')
    state = hass.states.get("sensor.test")
    assert state.state == "21"

    # ignore empty value, native sensor value should not change
    async_fire_mqtt_message(hass, "test-topic", '{ "power": "", "current": 5.34 }')
    state = hass.states.get("sensor.test")
    assert state.state == "21"

    # omitting value, causing it to be ignored, native sensor value should not change (template warning will be logged though)
    async_fire_mqtt_message(hass, "test-topic", '{ "current": 5.34 }')
    state = hass.states.get("sensor.test")
    assert state.state == "21"


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
                sensor.DOMAIN: {
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

    state = hass.states.get("sensor.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")

    # State should be unavailable since expire_after is defined and > 0
    state = hass.states.get("sensor.test")
    assert state.state == STATE_UNAVAILABLE

    await expires_helper(hass, caplog)


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
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "unit_of_measurement": "fav unit",
                    "expire_after": "4",
                    "force_update": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    # State should be unavailable since expire_after is defined and > 0
    state = hass.states.get("sensor.test")
    assert state.state == STATE_UNAVAILABLE

    await expires_helper(hass, caplog)


async def expires_helper(hass: HomeAssistant, caplog) -> None:
    """Run the basic expiry code."""
    realnow = dt_util.utcnow()
    now = datetime(realnow.year + 1, 1, 1, 1, tzinfo=dt_util.UTC)
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(hass, "test-topic", "100")
        await hass.async_block_till_done()

    # Value was set correctly.
    state = hass.states.get("sensor.test")
    assert state.state == "100"

    # Time jump +3s
    now = now + timedelta(seconds=3)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is not yet expired
    state = hass.states.get("sensor.test")
    assert state.state == "100"

    # Next message resets timer
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(hass, "test-topic", "101")
        await hass.async_block_till_done()

    # Value was updated correctly.
    state = hass.states.get("sensor.test")
    assert state.state == "101"

    # Time jump +3s
    now = now + timedelta(seconds=3)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is not yet expired
    state = hass.states.get("sensor.test")
    assert state.state == "101"

    # Time jump +2s
    now = now + timedelta(seconds=2)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is expired now
    state = hass.states.get("sensor.test")
    assert state.state == STATE_UNAVAILABLE


async def test_setting_sensor_value_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of the value via MQTT with JSON payload."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "value_template": "{{ value_json.val }}",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "test-topic", '{ "val": "100" }')
    state = hass.states.get("sensor.test")

    assert state.state == "100"

    # Make sure the state is written when a sensor value is reset to ''
    async_fire_mqtt_message(hass, "test-topic", '{ "val": "" }')
    state = hass.states.get("sensor.test")

    assert state.state == ""


async def test_setting_sensor_value_via_mqtt_json_message_and_default_current_state(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of the value via MQTT with fall back to current state."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "value_template": "{{ value_json.val | is_defined }}-{{ value_json.par }}",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(
        hass, "test-topic", '{ "val": "valcontent", "par": "parcontent" }'
    )
    state = hass.states.get("sensor.test")

    assert state.state == "valcontent-parcontent"

    async_fire_mqtt_message(hass, "test-topic", '{ "par": "invalidcontent" }')
    state = hass.states.get("sensor.test")

    assert state.state == "valcontent-parcontent"


async def test_setting_sensor_last_reset_via_mqtt_message(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setting of the last_reset property via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_class": "total",
                    "state_topic": "test-topic",
                    "unit_of_measurement": "fav unit",
                    "last_reset_topic": "last-reset-topic",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "last-reset-topic", "2020-01-02 08:11:00")
    state = hass.states.get("sensor.test")
    assert state.attributes.get("last_reset") == "2020-01-02T08:11:00"
    assert "'last_reset_topic' must be same as 'state_topic'" in caplog.text
    assert (
        "'last_reset_value_template' must be set if 'last_reset_topic' is set"
        in caplog.text
    )


@pytest.mark.parametrize("datestring", ["2020-21-02 08:11:00", "Hello there!"])
async def test_setting_sensor_bad_last_reset_via_mqtt_message(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    datestring,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
) -> None:
    """Test the setting of the last_reset property via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_class": "total",
                    "state_topic": "test-topic",
                    "unit_of_measurement": "fav unit",
                    "last_reset_topic": "last-reset-topic",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "last-reset-topic", datestring)
    state = hass.states.get("sensor.test")
    assert state.attributes.get("last_reset") is None
    assert "Invalid last_reset message" in caplog.text


async def test_setting_sensor_empty_last_reset_via_mqtt_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of the last_reset property via MQTT."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_class": "total",
                    "state_topic": "test-topic",
                    "unit_of_measurement": "fav unit",
                    "last_reset_topic": "last-reset-topic",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "last-reset-topic", "")
    state = hass.states.get("sensor.test")
    assert state.attributes.get("last_reset") is None


async def test_setting_sensor_last_reset_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of the value via MQTT with JSON payload."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_class": "total",
                    "state_topic": "test-topic",
                    "unit_of_measurement": "fav unit",
                    "last_reset_topic": "last-reset-topic",
                    "last_reset_value_template": "{{ value_json.last_reset }}",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(
        hass, "last-reset-topic", '{ "last_reset": "2020-01-02 08:11:00" }'
    )
    state = hass.states.get("sensor.test")
    assert state.attributes.get("last_reset") == "2020-01-02T08:11:00"


@pytest.mark.parametrize("extra", [{}, {"last_reset_topic": "test-topic"}])
async def test_setting_sensor_last_reset_via_mqtt_json_message_2(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    extra,
) -> None:
    """Test the setting of the value via MQTT with JSON payload."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    **{
                        "name": "test",
                        "state_class": "total",
                        "state_topic": "test-topic",
                        "unit_of_measurement": "kWh",
                        "value_template": "{{ value_json.value | float / 60000 }}",
                        "last_reset_value_template": "{{ utcnow().fromtimestamp(value_json.time / 1000, tz=utcnow().tzinfo) }}",
                    },
                    **extra,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(
        hass,
        "test-topic",
        '{"type":"minute","time":1629385500000,"value":947.7706166666667}',
    )
    state = hass.states.get("sensor.test")
    assert float(state.state) == pytest.approx(0.015796176944444445)
    assert state.attributes.get("last_reset") == "2021-08-19T15:05:00+00:00"
    assert "'last_reset_topic' must be same as 'state_topic'" not in caplog.text
    assert (
        "'last_reset_value_template' must be set if 'last_reset_topic' is set"
        not in caplog.text
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
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "unit_of_measurement": "fav unit",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    events = []

    @callback
    def test_callback(event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, test_callback)

    async_fire_mqtt_message(hass, "test-topic", "100")
    await hass.async_block_till_done()
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "100")
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
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "unit_of_measurement": "fav unit",
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
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, test_callback)

    async_fire_mqtt_message(hass, "test-topic", "100")
    await hass.async_block_till_done()
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "100")
    await hass.async_block_till_done()
    assert len(events) == 2


async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_list_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_list_payload(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_list_payload_all(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_list_payload_all(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_list_payload_any(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_list_payload_any(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_list_single(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test availability list and availability_topic are mutually exclusive."""
    await help_test_default_availability_list_single(
        hass,
        caplog,
        sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_availability(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability discovery update."""
    await help_test_discovery_update_availability(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_invalid_device_class(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device_class option with invalid value."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "device_class": "foobarnotreal",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("sensor.test")
    assert state is None


async def test_valid_device_class(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device_class option with valid values."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: [
                    {
                        "name": "Test 1",
                        "state_topic": "test-topic",
                        "device_class": "temperature",
                    },
                    {"name": "Test 2", "state_topic": "test-topic"},
                    {
                        "name": "Test 3",
                        "state_topic": "test-topic",
                        "device_class": None,
                    },
                ]
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("sensor.test_1")
    assert state.attributes["device_class"] == "temperature"
    state = hass.states.get("sensor.test_2")
    assert "device_class" not in state.attributes
    state = hass.states.get("sensor.test_3")
    assert "device_class" not in state.attributes


async def test_invalid_state_class(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test state_class option with invalid value."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "state_class": "foobarnotreal",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("sensor.test")
    assert state is None


async def test_valid_state_class(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test state_class option with valid values."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: [
                    {
                        "name": "Test 1",
                        "state_topic": "test-topic",
                        "state_class": "measurement",
                    },
                    {"name": "Test 2", "state_topic": "test-topic"},
                    {
                        "name": "Test 3",
                        "state_topic": "test-topic",
                        "state_class": None,
                    },
                ]
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("sensor.test_1")
    assert state.attributes["state_class"] == "measurement"
    state = hass.states.get("sensor.test_2")
    assert "state_class" not in state.attributes
    state = hass.states.get("sensor.test_3")
    assert "state_class" not in state.attributes


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        sensor.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_SENSOR_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
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
        sensor.DOMAIN,
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
        sensor.DOMAIN,
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
        sensor.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one sensor per unique_id."""
    config = {
        mqtt.DOMAIN: {
            sensor.DOMAIN: [
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
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, config
    )


async def test_discovery_removal_sensor(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered sensor."""
    data = '{ "name": "test", "state_topic": "test_topic" }'
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, sensor.DOMAIN, data
    )


async def test_discovery_update_sensor_topic_template(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered sensor."""
    config = {"name": "test", "state_topic": "test_topic"}
    config1 = copy.deepcopy(config)
    config2 = copy.deepcopy(config)
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "sensor/state1"
    config2["state_topic"] = "sensor/state2"
    config1["value_template"] = "{{ value_json.state | int }}"
    config2["value_template"] = "{{ value_json.state | int * 2 }}"

    state_data1 = [
        ([("sensor/state1", '{"state":100}')], "100", None),
    ]
    state_data2 = [
        ([("sensor/state1", '{"state":1000}')], "100", None),
        ([("sensor/state1", '{"state":1000}')], "100", None),
        ([("sensor/state2", '{"state":100}')], "200", None),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        sensor.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_discovery_update_sensor_template(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered sensor."""
    config = {"name": "test", "state_topic": "test_topic"}
    config1 = copy.deepcopy(config)
    config2 = copy.deepcopy(config)
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "sensor/state1"
    config2["state_topic"] = "sensor/state1"
    config1["value_template"] = "{{ value_json.state | int }}"
    config2["value_template"] = "{{ value_json.state | int * 2 }}"

    state_data1 = [
        ([("sensor/state1", '{"state":100}')], "100", None),
    ]
    state_data2 = [
        ([("sensor/state1", '{"state":100}')], "200", None),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        sensor.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_discovery_update_unchanged_sensor(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered sensor."""
    data1 = '{ "name": "Beer", "state_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.sensor.MqttSensor.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            sensor.DOMAIN,
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
    data1 = '{ "name": "Beer", "state_topic": "test_topic#" }'
    data2 = '{ "name": "Milk", "state_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry_no_yaml_config, caplog, sensor.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT sensor device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT sensor device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry_with_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_hub(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT sensor device registry integration."""
    await mqtt_mock_entry_no_yaml_config()
    registry = dr.async_get(hass)
    hub = registry.async_get_or_create(
        config_entry_id="123",
        connections=set(),
        identifiers={("mqtt", "hub-id")},
        manufacturer="manufacturer",
        model="hub",
    )

    data = json.dumps(
        {
            "name": "Test 1",
            "state_topic": "test-topic",
            "device": {"identifiers": ["helloworld"], "via_device": "hub-id"},
            "unique_id": "veryunique",
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.via_device_id == hub.id


async def test_entity_debug_info(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT sensor debug info."""
    await help_test_entity_debug_info(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_max_messages(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT sensor debug info."""
    await help_test_entity_debug_info_max_messages(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG, None
    )


async def test_entity_debug_info_remove(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT sensor debug info."""
    await help_test_entity_debug_info_remove(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_update_entity_id(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT sensor debug info."""
    await help_test_entity_debug_info_update_entity_id(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_disabled_by_default(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test entity disabled by default."""
    await help_test_entity_disabled_by_default(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.no_fail_on_log_exception
async def test_entity_category(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test entity category."""
    await help_test_entity_category(
        hass, mqtt_mock_entry_no_yaml_config, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_value_template_with_entity_id(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the access to attributes in value_template via the entity_id."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                sensor.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "unit_of_measurement": "fav unit",
                    "value_template": '\
                {% if state_attr(entity_id, "friendly_name") == "test" %} \
                    {{ value | int + 1 }} \
                {% else %} \
                    {{ value }} \
                {% endif %}',
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "test-topic", "100")
    state = hass.states.get("sensor.test")

    assert state.state == "101"


async def test_reloadable(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Test reloading the MQTT platform."""
    domain = sensor.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


async def test_cleanup_triggers_and_restoring_state(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    freezer,
) -> None:
    """Test cleanup old triggers at reloading and restoring the state."""
    domain = sensor.DOMAIN
    config1 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][domain])
    config1["name"] = "test1"
    config1["expire_after"] = 30
    config1["state_topic"] = "test-topic1"
    config1["device_class"] = "temperature"
    config1["unit_of_measurement"] = UnitOfTemperature.FAHRENHEIT.value

    config2 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][domain])
    config2["name"] = "test2"
    config2["expire_after"] = 5
    config2["state_topic"] = "test-topic2"
    config2["device_class"] = "temperature"
    config2["unit_of_measurement"] = UnitOfTemperature.CELSIUS.value

    freezer.move_to("2022-02-02 12:01:00+01:00")

    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {mqtt.DOMAIN: {domain: [config1, config2]}},
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()
    async_fire_mqtt_message(hass, "test-topic1", "100")
    state = hass.states.get("sensor.test1")
    assert state.state == "38"  # 100 °F -> 38 °C

    async_fire_mqtt_message(hass, "test-topic2", "200")
    state = hass.states.get("sensor.test2")
    assert state.state == "200"

    freezer.move_to("2022-02-02 12:01:10+01:00")

    await help_test_reload_with_config(
        hass, caplog, tmp_path, {mqtt.DOMAIN: {domain: [config1, config2]}}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test1")
    assert state.state == "38"  # 100 °F -> 38 °C

    state = hass.states.get("sensor.test2")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "test-topic1", "80")
    state = hass.states.get("sensor.test1")
    assert state.state == "27"  # 80 °F -> 27 °C

    async_fire_mqtt_message(hass, "test-topic2", "201")
    state = hass.states.get("sensor.test2")
    assert state.state == "201"


async def test_skip_restoring_state_with_over_due_expire_trigger(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    freezer,
) -> None:
    """Test restoring a state with over due expire timer."""

    freezer.move_to("2022-02-02 12:02:00+01:00")
    domain = sensor.DOMAIN
    config3 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][domain])
    config3["name"] = "test3"
    config3["expire_after"] = 10
    config3["state_topic"] = "test-topic3"
    fake_state = State(
        "sensor.test3",
        "300",
        {},
        last_changed=datetime.fromisoformat("2022-02-02 12:01:35+01:00"),
    )
    fake_extra_data = MagicMock()
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))

    assert await async_setup_component(
        hass, mqtt.DOMAIN, {mqtt.DOMAIN: {domain: config3}}
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()
    state = hass.states.get("sensor.test3")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "2.21", None, "2.21"),
        ("state_topic", "beer", None, "beer"),
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
        sensor.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][sensor.DOMAIN],
        topic,
        value,
        attribute,
        attribute_value,
        skip_raw_test=True,
    )


async def test_setup_manual_entity_from_yaml(hass: HomeAssistant) -> None:
    """Test setup manual configured MQTT entity."""
    platform = sensor.DOMAIN
    await help_test_setup_manual_entity_from_yaml(hass, DEFAULT_CONFIG)
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    tmp_path: Path,
) -> None:
    """Test unloading the config entry."""
    domain = sensor.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry_with_yaml_config, tmp_path, domain, config
    )
