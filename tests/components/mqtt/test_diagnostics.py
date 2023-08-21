"""Test MQTT diagnostics."""
import json
from unittest.mock import ANY, patch

import pytest

from homeassistant.components import mqtt
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import async_fire_mqtt_message
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator, MqttMockHAClientGenerator

default_config = {
    "birth_message": {},
    "broker": "mock-broker",
}


@pytest.fixture(autouse=True)
def device_tracker_sensor_only():
    """Only setup the device_tracker and sensor platforms to speed up tests."""
    with patch(
        "homeassistant.components.mqtt.PLATFORMS",
        [Platform.DEVICE_TRACKER, Platform.SENSOR],
    ):
        yield


async def test_entry_diagnostics(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_client: ClientSessionGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test config entry diagnostics."""
    mqtt_mock = await mqtt_mock_entry()
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    mqtt_mock.connected = True

    await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "connected": True,
        "devices": [],
        "mqtt_config": default_config,
        "mqtt_debug_info": {"entities": [], "triggers": []},
    }

    # Discover a device with an entity and a trigger
    config_sensor = {
        "device": {"identifiers": ["0AFFD2"]},
        "platform": "mqtt",
        "state_topic": "foobar/sensor",
        "unique_id": "unique",
    }
    config_trigger = {
        "automation_type": "trigger",
        "device": {"identifiers": ["0AFFD2"]},
        "platform": "mqtt",
        "topic": "test-topic1",
        "type": "foo",
        "subtype": "bar",
    }
    data_sensor = json.dumps(config_sensor)
    data_trigger = json.dumps(config_trigger)

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data_sensor)
    async_fire_mqtt_message(
        hass, "homeassistant/device_automation/bla/config", data_trigger
    )
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    expected_debug_info = {
        "entities": [
            {
                "entity_id": "sensor.mqtt_sensor",
                "subscriptions": [{"topic": "foobar/sensor", "messages": []}],
                "discovery_data": {
                    "payload": config_sensor,
                    "topic": "homeassistant/sensor/bla/config",
                },
                "transmitted": [],
            }
        ],
        "triggers": [
            {
                "discovery_data": {
                    "payload": config_trigger,
                    "topic": "homeassistant/device_automation/bla/config",
                },
                "trigger_key": ["device_automation", "bla"],
            }
        ],
    }

    expected_device = {
        "disabled": False,
        "disabled_by": None,
        "entities": [
            {
                "device_class": None,
                "disabled": False,
                "disabled_by": None,
                "entity_category": None,
                "entity_id": "sensor.mqtt_sensor",
                "icon": None,
                "original_device_class": None,
                "original_icon": None,
                "state": {
                    "attributes": {"friendly_name": "MQTT Sensor"},
                    "entity_id": "sensor.mqtt_sensor",
                    "last_changed": ANY,
                    "last_updated": ANY,
                    "state": "unknown",
                },
                "unit_of_measurement": None,
            }
        ],
        "id": device_entry.id,
        "name": None,
        "name_by_user": None,
    }

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "connected": True,
        "devices": [expected_device],
        "mqtt_config": default_config,
        "mqtt_debug_info": expected_debug_info,
    }

    assert await get_diagnostics_for_device(
        hass, hass_client, config_entry, device_entry
    ) == {
        "connected": True,
        "device": expected_device,
        "mqtt_config": default_config,
        "mqtt_debug_info": expected_debug_info,
    }


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {},
            mqtt.CONF_PASSWORD: "hunter2",
            mqtt.CONF_USERNAME: "my_user",
        }
    ],
)
async def test_redact_diagnostics(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_client: ClientSessionGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test redacting diagnostics."""
    mqtt_mock = await mqtt_mock_entry()
    expected_config = dict(default_config)
    expected_config["password"] = "**REDACTED**"
    expected_config["username"] = "**REDACTED**"

    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    mqtt_mock.connected = True

    # Discover a device with a device tracker
    config_tracker = {
        "device": {"identifiers": ["0AFFD2"]},
        "platform": "mqtt",
        "state_topic": "foobar/device_tracker",
        "json_attributes_topic": "attributes-topic",
        "unique_id": "unique",
    }
    data_tracker = json.dumps(config_tracker)

    async_fire_mqtt_message(
        hass, "homeassistant/device_tracker/bla/config", data_tracker
    )
    await hass.async_block_till_done()

    location_data = '{"latitude":32.87336,"longitude": -117.22743, "gps_accuracy":1.5}'
    async_fire_mqtt_message(hass, "attributes-topic", location_data)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})

    expected_debug_info = {
        "entities": [
            {
                "entity_id": "device_tracker.mqtt_unique",
                "subscriptions": [
                    {
                        "topic": "attributes-topic",
                        "messages": [
                            {
                                "payload": location_data,
                                "qos": 0,
                                "retain": False,
                                "time": ANY,
                                "topic": "attributes-topic",
                            }
                        ],
                    },
                    {"topic": "foobar/device_tracker", "messages": []},
                ],
                "discovery_data": {
                    "payload": config_tracker,
                    "topic": "homeassistant/device_tracker/bla/config",
                },
                "transmitted": [],
            }
        ],
        "triggers": [],
    }

    expected_device = {
        "disabled": False,
        "disabled_by": None,
        "entities": [
            {
                "device_class": None,
                "disabled": False,
                "disabled_by": None,
                "entity_category": None,
                "entity_id": "device_tracker.mqtt_unique",
                "icon": None,
                "original_device_class": None,
                "original_icon": None,
                "state": {
                    "attributes": {
                        "gps_accuracy": 1.5,
                        "latitude": "**REDACTED**",
                        "longitude": "**REDACTED**",
                        "source_type": "gps",
                    },
                    "entity_id": "device_tracker.mqtt_unique",
                    "last_changed": ANY,
                    "last_updated": ANY,
                    "state": "home",
                },
                "unit_of_measurement": None,
            }
        ],
        "id": device_entry.id,
        "name": None,
        "name_by_user": None,
    }

    await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "connected": True,
        "devices": [expected_device],
        "mqtt_config": expected_config,
        "mqtt_debug_info": expected_debug_info,
    }

    assert await get_diagnostics_for_device(
        hass, hass_client, config_entry, device_entry
    ) == {
        "connected": True,
        "device": expected_device,
        "mqtt_config": expected_config,
        "mqtt_debug_info": expected_debug_info,
    }
