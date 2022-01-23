"""The tests for the MQTT button platform."""
import copy
import json
from unittest.mock import patch

import pytest
import yaml

from homeassistant import config as hass_config
from homeassistant.components import notify
from homeassistant.components.mqtt import DOMAIN
from homeassistant.const import CONF_NAME, SERVICE_RELOAD
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from tests.common import async_fire_mqtt_message, mock_device_registry

DEFAULT_CONFIG = {notify.DOMAIN: {"platform": "mqtt", "command_topic": "test-topic"}}

COMMAND_TEMPLATE_TEST_PARAMS = (
    "name,service,parameters,expected_result",
    [
        (
            None,
            "lcd_set",
            {
                notify.ATTR_TITLE: "Title",
                notify.ATTR_MESSAGE: "Message",
                notify.ATTR_DATA: {"par1": "val1"},
            },
            '{"message":"Message",'
            '"name":"None",'
            '"service":"lcd_set",'
            '"par1":"val1",'
            '"target":['
            "'t1', 't2'"
            "],"
            '"title":"Title"}',
        ),
        (
            None,
            "lcd_set",
            {
                notify.ATTR_TITLE: "Title",
                notify.ATTR_MESSAGE: "Message",
                notify.ATTR_DATA: {"par1": "val1"},
                notify.ATTR_TARGET: ["t2"],
            },
            '{"message":"Message",'
            '"name":"None",'
            '"service":"lcd_set",'
            '"par1":"val1",'
            '"target":['
            "'t2'"
            "],"
            '"title":"Title"}',
        ),
        (
            None,
            "lcd_set_t1",
            {
                notify.ATTR_TITLE: "Title",
                notify.ATTR_MESSAGE: "Message",
                notify.ATTR_DATA: {"par1": "val2"},
            },
            '{"message":"Message",'
            '"name":"None",'
            '"service":"lcd_set",'
            '"par1":"val2",'
            '"target":['
            "'t1'"
            "],"
            '"title":"Title"}',
        ),
        (
            "My service",
            "my_service_t1",
            {
                notify.ATTR_TITLE: "Title",
                notify.ATTR_MESSAGE: "Message",
                notify.ATTR_DATA: {"par1": "val2"},
            },
            '{"message":"Message",'
            '"name":"My service",'
            '"service":"my_service",'
            '"par1":"val2",'
            '"target":['
            "'t1'"
            "],"
            '"title":"Title"}',
        ),
    ],
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


async def test_sending_mqtt_commands(hass, mqtt_mock, caplog):
    """Test the sending MQTT commands."""
    config1 = {
        "command_topic": "command-topic1",
        "name": "test1",
        "platform": "mqtt",
        "qos": "2",
    }
    config2 = {
        "command_topic": "command-topic2",
        "name": "test2",
        "targets": ["t1", "t2"],
        "platform": "mqtt",
        "qos": "2",
    }
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {notify.DOMAIN: [config1, config2]},
    )
    await hass.async_block_till_done()
    assert "<Event service_registered[L]: domain=notify, service=test1>" in caplog.text
    assert "<Event service_registered[L]: domain=notify, service=test2>" in caplog.text
    assert (
        "<Event service_registered[L]: domain=notify, service=test2_t1>" in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=test2_t2>" in caplog.text
    )

    # test1 simple call without targets
    await hass.services.async_call(
        notify.DOMAIN,
        "test1",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic1", "Message", 2, False
    )
    mqtt_mock.async_publish.reset_mock()

    # test2 simple call without targets
    await hass.services.async_call(
        notify.DOMAIN,
        "test2",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic2", "Message", 2, False
    )
    mqtt_mock.async_publish.reset_mock()

    # test2 simple call main service without target
    await hass.services.async_call(
        notify.DOMAIN,
        "test2",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic2", "Message", 2, False
    )
    mqtt_mock.async_publish.reset_mock()

    # test2 simple call main service with empty target
    await hass.services.async_call(
        notify.DOMAIN,
        "test2",
        {
            notify.ATTR_TITLE: "Title",
            notify.ATTR_MESSAGE: "Message",
            notify.ATTR_TARGET: [],
        },
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic2", "Message", 2, False
    )
    mqtt_mock.async_publish.reset_mock()

    # test2 simple call main service with single target
    await hass.services.async_call(
        notify.DOMAIN,
        "test2",
        {
            notify.ATTR_TITLE: "Title",
            notify.ATTR_MESSAGE: "Message",
            notify.ATTR_TARGET: ["t1"],
        },
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic2", "Message", 2, False
    )
    mqtt_mock.async_publish.reset_mock()

    # test2 simple call main service with invalid target
    await hass.services.async_call(
        notify.DOMAIN,
        "test2",
        {
            notify.ATTR_TITLE: "Title",
            notify.ATTR_MESSAGE: "Message",
            notify.ATTR_TARGET: ["invalid"],
        },
        blocking=True,
    )

    assert (
        "Cannot send Message, target list ['invalid'] is invalid, valid available targets: ['t1', 't2']"
        in caplog.text
    )
    mqtt_mock.async_publish.call_count == 0
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(*COMMAND_TEMPLATE_TEST_PARAMS)
async def test_sending_with_command_templates_with_config_setup(
    hass, mqtt_mock, caplog, name, service, parameters, expected_result
):
    """Test the sending MQTT commands using a template using config setup."""
    config = {
        "command_topic": "lcd/set",
        "command_template": "{"
        '"message":"{{message}}",'
        '"name":"{{name}}",'
        '"service":"{{service}}",'
        '"par1":"{{par1}}",'
        '"target":{{target}},'
        '"title":"{{title}}"'
        "}",
        "targets": ["t1", "t2"],
        "platform": "mqtt",
        "qos": "1",
    }
    if name:
        config[CONF_NAME] = name
    service_base_name = slugify(name) or "lcd_set"
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {notify.DOMAIN: config},
    )
    await hass.async_block_till_done()
    assert (
        f"<Event service_registered[L]: domain=notify, service={service_base_name}>"
        in caplog.text
    )
    assert (
        f"<Event service_registered[L]: domain=notify, service={service_base_name}_t1>"
        in caplog.text
    )
    assert (
        f"<Event service_registered[L]: domain=notify, service={service_base_name}_t2>"
        in caplog.text
    )
    await hass.services.async_call(
        notify.DOMAIN,
        service,
        parameters,
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "lcd/set", expected_result, 1, False
    )
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(*COMMAND_TEMPLATE_TEST_PARAMS)
async def test_sending_with_command_templates_auto_discovery(
    hass, mqtt_mock, caplog, name, service, parameters, expected_result
):
    """Test the sending MQTT commands using a template and auto discovery."""
    config = {
        "command_topic": "lcd/set",
        "command_template": "{"
        '"message":"{{message}}",'
        '"name":"{{name}}",'
        '"service":"{{service}}",'
        '"par1":"{{par1}}",'
        '"target":{{target}},'
        '"title":"{{title}}"'
        "}",
        "targets": ["t1", "t2"],
        "qos": "1",
    }
    if name:
        config[CONF_NAME] = name
    service_base_name = slugify(name) or "lcd_set"
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/bla/config", json.dumps(config)
    )
    await hass.async_block_till_done()
    assert (
        f"<Event service_registered[L]: domain=notify, service={service_base_name}>"
        in caplog.text
    )
    assert (
        f"<Event service_registered[L]: domain=notify, service={service_base_name}_t1>"
        in caplog.text
    )
    assert (
        f"<Event service_registered[L]: domain=notify, service={service_base_name}_t2>"
        in caplog.text
    )
    await hass.services.async_call(
        notify.DOMAIN,
        service,
        parameters,
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "lcd/set", expected_result, 1, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_discovery(hass, mqtt_mock, caplog):
    """Test discovery, update and removal of notify service."""
    data = '{ "name": "Old name", "command_topic": "test_topic" }'
    data_update = '{ "command_topic": "test_topic_update", "name": "New name" }'
    data_update_with_targets1 = '{ "command_topic": "test_topic", "name": "My notify service", "targets": ["target1", "target2"] }'
    data_update_with_targets2 = '{ "command_topic": "test_topic", "name": "My notify service", "targets": ["target1", "target3"] }'

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

    # rediscover with targets
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/bla/config", data_update_with_targets1
    )
    await hass.async_block_till_done()

    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service_target1>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service_target2>"
        in caplog.text
    )
    caplog.clear()
    # update available targets
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/bla/config", data_update_with_targets2
    )
    await hass.async_block_till_done()

    assert (
        "<Event service_removed[L]: domain=notify, service=my_notify_service_target2>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service_target3>"
        in caplog.text
    )
    caplog.clear()


async def test_discovery_with_device(hass, mqtt_mock, caplog, device_reg):
    """Test discovery, update and removal of notify service with a device config."""
    data = '{ "command_topic": "test_topic", "name": "My notify service", "targets": ["target1", "target2"], "device":{"identifiers":["LCD_61236812_ADBA"], "name": "Name" } }'
    data_device_update = '{ "command_topic": "test_topic", "name": "My notify service", "targets": ["target1", "target2"], "device":{"identifiers":["LCD_61236812_ADBA"], "name": "Name update" } }'
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", data)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is not None
    device_id = device_entry.id
    assert (
        f"<Event device_registry_updated[L]: action=create, device_id={device_id}>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service_target1>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service_target2>"
        in caplog.text
    )
    caplog.clear()

    # Test device update
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/bla/config", data_device_update
    )
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is not None
    assert device_id == device_entry.id
    assert (
        f"<Event device_registry_updated[L]: action=update, device_id={device_id}>"
        in caplog.text
    )
    caplog.clear()

    # Test removal device from device registry
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", "{}")
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is None
    assert (
        "<Event service_removed[L]: domain=notify, service=my_notify_service>"
        in caplog.text
    )
    assert (
        "<Event service_removed[L]: domain=notify, service=my_notify_service_target1>"
        in caplog.text
    )
    assert (
        "<Event service_removed[L]: domain=notify, service=my_notify_service_target2>"
        in caplog.text
    )
    assert (
        f"<Event device_registry_updated[L]: action=remove, device_id={device_id}>"
        in caplog.text
    )
    caplog.clear()

    # Re-create the device again
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/bla/config", data)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is not None
    device_id = device_entry.id
    assert (
        f"<Event device_registry_updated[L]: action=create, device_id={device_id}>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service_target1>"
        in caplog.text
    )
    assert (
        "<Event service_registered[L]: domain=notify, service=my_notify_service_target2>"
        in caplog.text
    )
    caplog.clear()

    # Remove the device from the device registry
    device_reg.async_remove_device(device_id)
    await hass.async_block_till_done()
    assert (
        f"<Event device_registry_updated[L]: action=remove, device_id={device_id}>"
        in caplog.text
    )
    assert (
        "<Event service_removed[L]: domain=notify, service=my_notify_service>"
        in caplog.text
    )
    assert (
        "<Event service_removed[L]: domain=notify, service=my_notify_service_target1>"
        in caplog.text
    )
    assert (
        "<Event service_removed[L]: domain=notify, service=my_notify_service_target2>"
        in caplog.text
    )
    assert (
        f"<Event device_registry_updated[L]: action=remove, device_id={device_id}>"
        in caplog.text
    )
    assert "Notify service ('notify', 'bla') has been removed" in caplog.text
    caplog.clear()


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
