"""Common test objects."""
import json
from unittest.mock import ANY

from homeassistant.components import mqtt
from homeassistant.components.mqtt.discovery import async_start

from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_mock_mqtt_component,
    async_setup_component,
    mock_registry,
)


async def help_test_setting_attribute_via_mqtt_json_message(
    hass, mqtt_mock, domain, config
):
    """Test the setting of attribute via MQTT with JSON payload.

    This is a test helper for the MqttAttributes mixin.
    """
    assert await async_setup_component(hass, domain, config,)

    async_fire_mqtt_message(hass, "attr-topic", '{ "val": "100" }')
    state = hass.states.get(f"{domain}.test")

    assert state.attributes.get("val") == "100"


async def help_test_update_with_json_attrs_not_dict(
    hass, mqtt_mock, caplog, domain, config
):
    """Test attributes get extracted from a JSON result.

    This is a test helper for the MqttAttributes mixin.
    """
    assert await async_setup_component(hass, domain, config,)

    async_fire_mqtt_message(hass, "attr-topic", '[ "list", "of", "things"]')
    state = hass.states.get(f"{domain}.test")

    assert state.attributes.get("val") is None
    assert "JSON result was not a dictionary" in caplog.text


async def help_test_update_with_json_attrs_bad_JSON(
    hass, mqtt_mock, caplog, domain, config
):
    """Test JSON validation of attributes.

    This is a test helper for the MqttAttributes mixin.
    """
    assert await async_setup_component(hass, domain, config,)

    async_fire_mqtt_message(hass, "attr-topic", "This is not JSON")

    state = hass.states.get(f"{domain}.test")
    assert state.attributes.get("val") is None
    assert "Erroneous JSON: This is not JSON" in caplog.text


async def help_test_discovery_update_attr(
    hass, mqtt_mock, caplog, domain, data1, data2
):
    """Test update of discovered MQTTAttributes.

    This is a test helper for the MqttAttributes mixin.
    """
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "100" }')
    state = hass.states.get(f"{domain}.test")
    assert state.attributes.get("val") == "100"

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "50" }')
    state = hass.states.get(f"{domain}.test")
    assert state.attributes.get("val") == "100"

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "attr-topic2", '{ "val": "75" }')
    state = hass.states.get(f"{domain}.test")
    assert state.attributes.get("val") == "75"


async def help_test_unique_id(hass, domain, config):
    """Test unique id option only creates one entity per unique_id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, domain, config,)
    async_fire_mqtt_message(hass, "test-topic", "payload")
    assert len(hass.states.async_entity_ids(domain)) == 1


async def help_test_discovery_removal(hass, mqtt_mock, caplog, domain, data):
    """Test removal of discovered component.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert state.name == "test"

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", "")
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is None


async def help_test_discovery_update(hass, mqtt_mock, caplog, domain, data1, data2):
    """Test update of discovered component.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Beer"

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Milk"

    state = hass.states.get(f"{domain}.milk")
    assert state is None


async def help_test_discovery_broken(hass, mqtt_mock, caplog, domain, data1, data2):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is None

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.milk")
    assert state is not None
    assert state.name == "Milk"
    state = hass.states.get(f"{domain}.beer")
    assert state is None


async def help_test_entity_device_info_with_identifier(hass, mqtt_mock, domain, config):
    """Test device registry integration.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.identifiers == {("mqtt", "helloworld")}
    assert device.connections == {("mac", "02:5b:26:a8:dc:12")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.sw_version == "0.1-beta"


async def help_test_entity_device_info_update(hass, mqtt_mock, domain, config):
    """Test device registry update.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.name == "Beer"

    config["device"]["name"] = "Milk"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.name == "Milk"


async def help_test_entity_id_update(hass, mqtt_mock, domain, config):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    registry = mock_registry(hass, {})
    mock_mqtt = await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, domain, config,)

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call("test-topic", ANY, 0, "utf-8")
    mock_mqtt.async_subscribe.assert_any_call("avty-topic", ANY, 0, "utf-8")
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity(f"{domain}.beer", new_entity_id=f"{domain}.milk")
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is None

    state = hass.states.get(f"{domain}.milk")
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call("test-topic", ANY, 0, "utf-8")
    mock_mqtt.async_subscribe.assert_any_call("avty-topic", ANY, 0, "utf-8")
