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

DEFAULT_CONFIG = {
    notify.DOMAIN: {"platform": "mqtt", "target": "test", "command_topic": "test-topic"}
}


async def test_sending_mqtt_commands(hass, mqtt_mock, caplog):
    """Test the sending MQTT commands."""
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: {
                "command_topic": "command-topic",
                "name": "test",
                "target": "test",
                "platform": "mqtt",
                "qos": "2",
            }
        },
    )
    await hass.async_block_till_done()
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_test>" in caplog.text
    )
    assert "<Event service_registered[L]: domain=notify, service=mqtt>" in caplog.text

    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}_test",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "Message", 2, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_discovery(hass, mqtt_mock, caplog):
    """Test discovery, update and removal of notify service."""
    data = '{ "target": "test", "command_topic": "test_topic" }'
    data_update = (
        '{ "target": "test", "command_topic": "test_topic_update", "name": "New name" }'
    )

    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", data)
    await hass.async_block_till_done()

    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_test>" in caplog.text
    )

    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}_test",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("test_topic", "Message", 0, False)
    mqtt_mock.async_publish.reset_mock()

    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/bla/config", data_update
    )
    await hass.async_block_till_done()

    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_new_name>"
        in caplog.text
    )
    assert "<Event service_removed[L]: domain=notify, service=mqtt_test>" in caplog.text

    assert (
        "Notify service ('notify', 'bla') for target test has been updated"
        in caplog.text
    )

    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}_new_name",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "test_topic_update", "Message", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", "")
    await hass.async_block_till_done()

    assert "<Event service_removed[L]: domain=notify, service=mqtt_test>" in caplog.text


async def test_publishing_with_custom_encoding(hass, mqtt_mock, caplog):
    """Test publishing MQTT payload with different encoding."""
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: {
                "command_topic": "command-topic",
                "name": "test",
                "target": "test",
                "platform": "mqtt",
                "qos": "2",
            }
        },
    )
    await hass.async_block_till_done()

    data = '{"target": "test", "command_topic": "test_topic", "command_template": "{{ pack(int(message), \'b\') }}" }'
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", data)
    await hass.async_block_till_done()

    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_test>" in caplog.text
    )

    # test raw payload
    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}_test",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "4"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with("test_topic", b"\x04", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # test with utf-16
    data = '{"encoding":"utf-16", "target": "test", "command_topic": "test_topic", "command_template": "{{ message }}" }'
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", data)
    await hass.async_block_till_done()

    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}_test",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_topic", "Message".encode("utf-16"), 0, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_reloadable(hass, mqtt_mock, caplog, tmp_path):
    """Test reloading the MQTT platform."""
    domain = notify.DOMAIN
    config = DEFAULT_CONFIG[domain]

    # Create and test an old config of 2 entities based on the config supplied
    old_config_1 = copy.deepcopy(config)
    old_config_1["name"] = "test_old_1"
    old_config_1["target"] = "test_old_1"
    old_config_2 = copy.deepcopy(config)
    old_config_2["name"] = "test_old_2"
    old_config_2["target"] = "test_old_2"

    assert await async_setup_component(hass, domain, {domain: old_config_1})
    await hass.async_block_till_done()
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_test_old_1>"
        in caplog.text
    )
    assert await async_setup_component(hass, domain, {domain: old_config_2})
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_test_old_2>"
        in caplog.text
    )
    caplog.clear()

    # Create temporary fixture for configuration.yaml based on the supplied config and test a reload with this new config
    new_config_1 = copy.deepcopy(config)
    new_config_1["name"] = "test_new_1"
    new_config_1["target"] = "test_new_1"
    new_config_2 = copy.deepcopy(config)
    new_config_2["name"] = "test_new_2"
    new_config_2["target"] = "test_new_2"
    new_config_3 = copy.deepcopy(config)
    new_config_3["name"] = "test_new_3"
    new_config_3["target"] = "test_new_3"
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump({domain: [new_config_1, new_config_2, new_config_3]})
    new_yaml_config_file.write_text(new_yaml_config)
    assert new_yaml_config_file.read_text() == new_yaml_config

    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file):
        await hass.services.async_call(
            "mqtt",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert "<Event event_mqtt_reloaded[L]>" in caplog.text

    assert len(hass.states.async_all(domain)) == 3

    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_test_new_1>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_test_new_2>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_test_new_3>"
        in caplog.text
    )
    caplog.clear()
