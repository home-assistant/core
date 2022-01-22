"""The tests for the MQTT button platform."""
import copy
from unittest.mock import patch

import yaml

from homeassistant import config as hass_config
from homeassistant.components import notify
from homeassistant.components.mqtt import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.setup import async_setup_component

from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {notify.DOMAIN: {"platform": "mqtt", "command_topic": "test-topic"}}


async def test_sending_mqtt_commands(hass, mqtt_mock, caplog):
    """Test the sending MQTT commands."""
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: {
                "command_topic": "command-topic",
                "name": "test",
                "platform": "mqtt",
                "qos": "2",
            }
        },
    )
    await hass.async_block_till_done()
    assert "<Event service_registered[L]: domain=notify, service=test>" in caplog.text

    await hass.services.async_call(
        notify.DOMAIN,
        "test",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "Message", 2, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_discovery(hass, mqtt_mock, caplog):
    """Test discovery, update and removal of notify service."""
    data = '{ "name": "Old name", "command_topic": "test_topic" }'
    data_update = '{ "command_topic": "test_topic_update", "name": "New name" }'

    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", data)
    await hass.async_block_till_done()

    assert (
        "<Event service_registered[L]: domain=notify, service=old_name>" in caplog.text
    )

    await hass.services.async_call(
        notify.DOMAIN,
        "old_name",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("test_topic", "Message", 0, False)
    mqtt_mock.async_publish.reset_mock()

    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/bla/config", data_update
    )
    await hass.async_block_till_done()

    assert "<Event service_removed[L]: domain=notify, service=old_name>" in caplog.text
    assert (
        "<Event service_registered[L]: domain=notify, service=new_name>" in caplog.text
    )

    assert "Notify service ('notify', 'bla') has been updated" in caplog.text

    await hass.services.async_call(
        notify.DOMAIN,
        "new_name",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "test_topic_update", "Message", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", "")
    await hass.async_block_till_done()

    assert "<Event service_removed[L]: domain=notify, service=new_name>" in caplog.text


async def test_publishing_with_custom_encoding(hass, mqtt_mock, caplog):
    """Test publishing MQTT payload with different encoding via discovery and configuration."""
    # test with default encoding using configuration setup
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: {
                "command_topic": "command-topic",
                "name": "test",
                "platform": "mqtt",
                "qos": "2",
            }
        },
    )
    await hass.async_block_till_done()

    # test with raw encoding and discovery
    data = '{"name": "test2", "command_topic": "test_topic2", "command_template": "{{ pack(int(message), \'b\') }}" }'
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", data)
    await hass.async_block_till_done()

    assert "Notify service ('notify', 'bla') has been initialized" in caplog.text
    assert "<Event service_registered[L]: domain=notify, service=test2>" in caplog.text

    await hass.services.async_call(
        notify.DOMAIN,
        "test2",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "4"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with("test_topic2", b"\x04", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # test with utf-16 and update discovery
    data = '{"encoding":"utf-16", "name": "test3", "command_topic": "test_topic3", "command_template": "{{ message }}" }'
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", data)
    await hass.async_block_till_done()
    assert (
        "Component has already been discovered: notify bla, sending update"
        in caplog.text
    )

    await hass.services.async_call(
        notify.DOMAIN,
        "test3",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_topic3", "Message".encode("utf-16"), 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", "")
    await hass.async_block_till_done()

    assert "Notify service ('notify', 'bla') has been removed" in caplog.text


async def test_reloadable(hass, mqtt_mock, caplog, tmp_path):
    """Test reloading the MQTT platform."""
    domain = notify.DOMAIN
    config = DEFAULT_CONFIG[domain]

    # Create and test an old config of 2 entities based on the config supplied
    old_config_1 = copy.deepcopy(config)
    old_config_1["name"] = "Test old 1"
    old_config_2 = copy.deepcopy(config)
    old_config_2["name"] = "Test old 2"

    assert await async_setup_component(
        hass, domain, {domain: [old_config_1, old_config_2]}
    )
    await hass.async_block_till_done()
    assert (
        "<Event service_registered[L]: domain=notify, service=test_old_1>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=test_old_2>"
        in caplog.text
    )
    caplog.clear()

    # Add an auto discovered notify target
    data = '{"name": "Test old 3", "command_topic": "test_topic_discovery" }'
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", data)
    await hass.async_block_till_done()

    assert "Notify service ('notify', 'bla') has been initialized" in caplog.text
    assert (
        "<Event service_registered[L]: domain=notify, service=test_old_3>"
        in caplog.text
    )

    # Create temporary fixture for configuration.yaml based on the supplied config and test a reload with this new config
    new_config_1 = copy.deepcopy(config)
    new_config_1["name"] = "Test new 1"
    new_config_2 = copy.deepcopy(config)
    new_config_2["name"] = "test new 2"
    new_config_3 = copy.deepcopy(config)
    new_config_3["name"] = "test new 3"
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump({domain: [new_config_1, new_config_2, new_config_3]})
    new_yaml_config_file.write_text(new_yaml_config)
    assert new_yaml_config_file.read_text() == new_yaml_config

    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert (
        "<Event service_removed[L]: domain=notify, service=test_old_1>" in caplog.text
    )
    assert (
        "<Event service_removed[L]: domain=notify, service=test_old_2>" in caplog.text
    )

    assert (
        "<Event service_registered[L]: domain=notify, service=test_new_1>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=test_new_2>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=test_new_3>"
        in caplog.text
    )
    assert "<Event event_mqtt_reloaded[L]>" in caplog.text
    caplog.clear()

    # test if the auto discovered item survived the platform reload
    await hass.services.async_call(
        notify.DOMAIN,
        "test_old_3",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_topic_discovery", "Message", 0, False
    )

    mqtt_mock.async_publish.reset_mock()

    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", "")
    await hass.async_block_till_done()

    assert "Notify service ('notify', 'bla') has been removed" in caplog.text
