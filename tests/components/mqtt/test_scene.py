"""The tests for the MQTT scene platform."""
import copy
from unittest.mock import patch

import pytest

from homeassistant.components import scene
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_UNKNOWN, Platform
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
    help_test_reloadable,
    help_test_reloadable_late,
    help_test_setup_manual_entity_from_yaml,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
)

from tests.common import mock_restore_cache

DEFAULT_CONFIG = {
    scene.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "command_topic": "test-topic",
        "payload_on": "test-payload-on",
    }
}


@pytest.fixture(autouse=True)
def scene_platform_only():
    """Only setup the scene platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.SCENE]):
        yield


async def test_sending_mqtt_commands(hass, mqtt_mock_entry_with_yaml_config):
    """Test the sending MQTT commands."""
    fake_state = ha.State("scene.test", STATE_UNKNOWN)
    mock_restore_cache(hass, (fake_state,))

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
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("scene.test")
    assert state.state == STATE_UNKNOWN

    data = {ATTR_ENTITY_ID: "scene.test"}
    await hass.services.async_call(scene.DOMAIN, SERVICE_TURN_ON, data, blocking=True)

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "beer on", 0, False
    )


async def test_availability_when_connection_lost(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, scene.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, scene.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
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
        hass,
        mqtt_mock_entry_with_yaml_config,
        scene.DOMAIN,
        config,
        True,
        "state-topic",
        "1",
    )


async def test_custom_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
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
        hass,
        mqtt_mock_entry_with_yaml_config,
        scene.DOMAIN,
        config,
        True,
        "state-topic",
        "1",
    )


async def test_unique_id(hass, mqtt_mock_entry_with_yaml_config):
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
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, scene.DOMAIN, config
    )


async def test_discovery_removal_scene(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test removal of discovered scene."""
    data = '{ "name": "test",' '  "command_topic": "test_topic" }'
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, scene.DOMAIN, data
    )


async def test_discovery_update_payload(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test update of discovered scene."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[scene.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[scene.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["payload_on"] = "ON"
    config2["payload_on"] = "ACTIVATE"

    await help_test_discovery_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        scene.DOMAIN,
        config1,
        config2,
    )


async def test_discovery_update_unchanged_scene(
    hass, mqtt_mock_entry_no_yaml_config, caplog
):
    """Test update of discovered scene."""
    data1 = '{ "name": "Beer",' '  "command_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.scene.MqttScene.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            scene.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk",' '  "command_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry_no_yaml_config, caplog, scene.DOMAIN, data1, data2
    )


async def test_reloadable(hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path):
    """Test reloading the MQTT platform."""
    domain = scene.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


async def test_reloadable_late(hass, mqtt_client_mock, caplog, tmp_path):
    """Test reloading the MQTT platform with late entry setup."""
    domain = scene.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable_late(hass, caplog, tmp_path, domain, config)


async def test_setup_manual_entity_from_yaml(hass):
    """Test setup manual configured MQTT entity."""
    platform = scene.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG[platform])
    config["name"] = "test"
    del config["platform"]
    await help_test_setup_manual_entity_from_yaml(hass, platform, config)
    assert hass.states.get(f"{platform}.test") is not None


async def test_unload_entry(hass, mqtt_mock_entry_with_yaml_config, tmp_path):
    """Test unloading the config entry."""
    domain = scene.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry_with_yaml_config, tmp_path, domain, config
    )
