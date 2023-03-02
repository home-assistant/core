"""The tests for mqtt camera component."""
from base64 import b64encode
from http import HTTPStatus
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components import camera, mqtt
from homeassistant.components.mqtt.camera import MQTT_CAMERA_ATTRIBUTES_BLOCKED
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
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

from tests.common import async_fire_mqtt_message
from tests.typing import ClientSessionGenerator, MqttMockHAClientGenerator

DEFAULT_CONFIG = {mqtt.DOMAIN: {camera.DOMAIN: {"name": "test", "topic": "test_topic"}}}


@pytest.fixture(autouse=True)
def camera_platform_only():
    """Only setup the camera platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.CAMERA]):
        yield


async def test_run_camera_setup(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
) -> None:
    """Test that it fetches the given payload."""
    topic = "test/camera"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {mqtt.DOMAIN: {camera.DOMAIN: {"topic": topic, "name": "Test Camera"}}},
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    url = hass.states.get("camera.test_camera").attributes["entity_picture"]

    async_fire_mqtt_message(hass, topic, "beer")

    client = await hass_client_no_auth()
    resp = await client.get(url)
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "beer"


async def test_run_camera_b64_encoded(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
) -> None:
    """Test that it fetches the given encoded payload."""
    topic = "test/camera"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                camera.DOMAIN: {
                    "topic": topic,
                    "name": "Test Camera",
                    "image_encoding": "b64",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    url = hass.states.get("camera.test_camera").attributes["entity_picture"]

    async_fire_mqtt_message(hass, topic, b64encode(b"grass"))

    client = await hass_client_no_auth()
    resp = await client.get(url)
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "grass"


async def test_camera_b64_encoded_with_availability(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
) -> None:
    """Test availability works if b64 encoding is turned on."""
    topic = "test/camera"
    topic_availability = "test/camera_availability"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                "camera": {
                    "topic": topic,
                    "name": "Test Camera",
                    "encoding": "utf-8",
                    "image_encoding": "b64",
                    "availability": {"topic": topic_availability},
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    # Make sure we are available
    async_fire_mqtt_message(hass, topic_availability, "online")

    url = hass.states.get("camera.test_camera").attributes["entity_picture"]

    async_fire_mqtt_message(hass, topic, b64encode(b"grass"))

    client = await hass_client_no_auth()
    resp = await client.get(url)
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "grass"


async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry_with_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        camera.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_CAMERA_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry_with_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
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
        camera.DOMAIN,
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
        camera.DOMAIN,
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
        camera.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one camera per unique_id."""
    config = {
        mqtt.DOMAIN: {
            camera.DOMAIN: [
                {
                    "name": "Test 1",
                    "topic": "test-topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
                {
                    "name": "Test 2",
                    "topic": "test-topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
            ]
        }
    }
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, camera.DOMAIN, config
    )


async def test_discovery_removal_camera(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered camera."""
    data = json.dumps(DEFAULT_CONFIG[mqtt.DOMAIN][camera.DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, camera.DOMAIN, data
    )


async def test_discovery_update_camera(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered camera."""
    config1 = {"name": "Beer", "topic": "test_topic"}
    config2 = {"name": "Milk", "topic": "test_topic"}

    await help_test_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, caplog, camera.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_camera(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered camera."""
    data1 = '{ "name": "Beer", "topic": "test_topic"}'
    with patch(
        "homeassistant.components.mqtt.camera.MqttCamera.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            camera.DOMAIN,
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
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "topic": "test_topic"}'

    await help_test_discovery_broken(
        hass, mqtt_mock_entry_no_yaml_config, caplog, camera.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT camera device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry_no_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT camera device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry_no_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry_no_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry_no_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass,
        mqtt_mock_entry_with_yaml_config,
        camera.DOMAIN,
        DEFAULT_CONFIG,
        ["test_topic"],
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        camera.DOMAIN,
        DEFAULT_CONFIG,
        None,
        state_topic="test_topic",
        state_payload=b"ON",
    )


async def test_reloadable(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Test reloading the MQTT platform."""
    domain = camera.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


async def test_setup_manual_entity_from_yaml(hass: HomeAssistant) -> None:
    """Test setup manual configured MQTT entity."""
    platform = camera.DOMAIN
    await help_test_setup_manual_entity_from_yaml(hass, DEFAULT_CONFIG)
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    tmp_path: Path,
) -> None:
    """Test unloading the config entry."""
    domain = camera.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry_with_yaml_config, tmp_path, domain, config
    )
