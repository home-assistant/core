"""The tests for mqtt camera component."""
import json

from homeassistant.components import camera, mqtt
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.setup import async_setup_component

from .test_common import (
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_mock_mqtt_component,
)

DEFAULT_CONFIG = {
    camera.DOMAIN: {"platform": "mqtt", "name": "test", "topic": "test_topic"}
}


async def test_run_camera_setup(hass, aiohttp_client):
    """Test that it fetches the given payload."""
    topic = "test/camera"
    await async_mock_mqtt_component(hass)
    await async_setup_component(
        hass,
        "camera",
        {"camera": {"platform": "mqtt", "topic": topic, "name": "Test Camera"}},
    )

    url = hass.states.get("camera.test_camera").attributes["entity_picture"]

    async_fire_mqtt_message(hass, topic, "beer")

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(url)
    assert resp.status == 200
    body = await resp.text()
    assert body == "beer"


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass):
    """Test unique id option only creates one camera per unique_id."""
    config = {
        camera.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, camera.DOMAIN, config)


async def test_discovery_removal_camera(hass, mqtt_mock, caplog):
    """Test removal of discovered camera."""
    data = json.dumps(DEFAULT_CONFIG[camera.DOMAIN])
    await help_test_discovery_removal(hass, mqtt_mock, caplog, camera.DOMAIN, data)


async def test_discovery_update_camera(hass, mqtt_mock, caplog):
    """Test update of discovered camera."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)

    data1 = '{ "name": "Beer",' '  "topic": "test_topic"}'
    data2 = '{ "name": "Milk",' '  "topic": "test_topic"}'

    await help_test_discovery_update(
        hass, mqtt_mock, caplog, camera.DOMAIN, data1, data2
    )


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)

    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk",' '  "topic": "test_topic"}'

    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, camera.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT camera device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT camera device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG, ["test_topic"]
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, camera.DOMAIN, DEFAULT_CONFIG, "test_topic", b"ON"
    )
