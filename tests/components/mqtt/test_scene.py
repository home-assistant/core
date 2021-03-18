"""The tests for the MQTT scene platform."""
import copy
import json
from unittest.mock import patch

import pytest

from homeassistant.components import scene
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
import homeassistant.core as ha
from homeassistant.setup import async_setup_component

from .test_common import (
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_unchanged,
    help_test_unique_id,
)

DEFAULT_CONFIG = {
    scene.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "command_topic": "test-topic",
        "payload_on": "test-payload-on",
    }
}


async def test_sending_mqtt_commands(hass, mqtt_mock):
    """Test the sending MQTT commands."""
    fake_state = ha.State("scene.test", scene.STATE)

    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=fake_state,
    ):
        assert await async_setup_component(
            hass,
            scene.DOMAIN,
            {
                scene.DOMAIN: {
                    "platform": "mqtt",
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_on": "beer on",
                },
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("scene.test")
    assert state.state == scene.STATE

    data = {ATTR_ENTITY_ID: "scene.test"}
    await hass.services.async_call(scene.DOMAIN, SERVICE_TURN_ON, data, blocking=True)

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "beer on", 0, False
    )


async def test_availability_when_connection_lost(hass, mqtt_mock):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock, scene.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, scene.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    config = {
        scene.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "command-topic",
            "payload_on": 1,
        }
    }

    await help_test_default_availability_payload(
        hass, mqtt_mock, scene.DOMAIN, config, True, "state-topic", "1"
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    config = {
        scene.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "command-topic",
            "payload_on": 1,
        }
    }

    await help_test_custom_availability_payload(
        hass, mqtt_mock, scene.DOMAIN, config, True, "state-topic", "1"
    )


async def test_unique_id(hass, mqtt_mock):
    """Test unique id option only creates one scene per unique_id."""
    config = {
        scene.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, mqtt_mock, scene.DOMAIN, config)


async def test_discovery_removal_scene(hass, mqtt_mock, caplog):
    """Test removal of discovered scene."""
    data = '{ "name": "test",' '  "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock, caplog, scene.DOMAIN, data)


async def test_discovery_update_payload(hass, mqtt_mock, caplog):
    """Test update of discovered scene."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[scene.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[scene.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["payload_on"] = "ON"
    config2["payload_on"] = "ACTIVATE"

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    await help_test_discovery_update(
        hass,
        mqtt_mock,
        caplog,
        scene.DOMAIN,
        data1,
        data2,
    )


async def test_discovery_update_unchanged_scene(hass, mqtt_mock, caplog):
    """Test update of discovered scene."""
    data1 = '{ "name": "Beer",' '  "command_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.scene.MqttScene.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, scene.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk",' '  "command_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, scene.DOMAIN, data1, data2
    )
