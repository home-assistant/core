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
from homeassistant.exceptions import ServiceNotFound
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from tests.common import async_fire_mqtt_message, mock_device_registry

DEFAULT_CONFIG = {notify.DOMAIN: {"platform": "mqtt", "command_topic": "test-topic"}}

COMMAND_TEMPLATE_TEST_PARAMS = (
    "name,service,parameters,expected_result",
    [
        (
            "My service",
            "my_service",
            {
                notify.ATTR_TITLE: "Title",
                notify.ATTR_MESSAGE: "Message",
                notify.ATTR_DATA: {"par1": "val1"},
            },
            '{"message":"Message",'
            '"name":"My service",'
            '"service":"my_service",'
            '"par1":"val1",'
            '"target":['
            "'t1', 't2'"
            "],"
            '"title":"Title"}',
        ),
        (
            "My service",
            "my_service",
            {
                notify.ATTR_TITLE: "Title",
                notify.ATTR_MESSAGE: "Message",
                notify.ATTR_DATA: {"par1": "val1"},
                notify.ATTR_TARGET: ["t2"],
            },
            '{"message":"Message",'
            '"name":"My service",'
            '"service":"my_service",'
            '"par1":"val1",'
            '"target":['
            "'t2'"
            "],"
            '"title":"Title"}',
        ),
        (
            "My service",
            "my_service_t1",
            {
                notify.ATTR_TITLE: "Title2",
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
            '"title":"Title2"}',
        ),
    ],
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


async def async_setup_notifify_service_with_auto_discovery(
    hass, mqtt_mock, caplog, device_reg, data, service_name
):
    """Test setup notify service with a device config."""
    caplog.clear()
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/{service_name}/config", data
    )
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is not None
    assert (
        f"<Event service_registered[L]: domain=notify, service={service_name}>"
        in caplog.text
    )
    assert (
        f"<Event service_registered[L]: domain=notify, service={service_name}_target1>"
        in caplog.text
    )
    assert (
        f"<Event service_registered[L]: domain=notify, service={service_name}_target2>"
        in caplog.text
    )


@pytest.mark.parametrize(*COMMAND_TEMPLATE_TEST_PARAMS)
async def test_sending_with_command_templates_with_config_setup(
    hass, mqtt_mock, caplog, name, service, parameters, expected_result
):
    """Test the sending MQTT commands using a template using config setup."""
    config = {
        "name": name,
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
    service_base_name = slugify(name)
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
        "name": name,
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
        service_base_name = slugify(name)
    else:
        service_base_name = DOMAIN
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


async def test_with_same_name(hass, mqtt_mock, caplog):
    """Test the multiple setups with the same name."""
    config1 = {
        "command_topic": "command-topic1",
        "name": "test_same_name",
        "platform": "mqtt",
        "qos": "2",
    }
    config2 = {
        "command_topic": "command-topic2",
        "name": "test_same_name",
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
    assert (
        "<Event service_registered[L]: domain=notify, service=test_same_name>"
        in caplog.text
    )
    assert (
        "Notify service 'test_same_name' already exists, cannot register service"
        in caplog.text
    )

    # test call main service on service with multiple targets with the same name
    # the first configured service should publish
    await hass.services.async_call(
        notify.DOMAIN,
        "test_same_name",
        {
            notify.ATTR_TITLE: "Title",
            notify.ATTR_MESSAGE: "Message",
        },
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic1", "Message", 2, False
    )
    mqtt_mock.async_publish.reset_mock()

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(
            notify.DOMAIN,
            "test_same_name_t2",
            {
                notify.ATTR_TITLE: "Title",
                notify.ATTR_MESSAGE: "Message",
                notify.ATTR_TARGET: ["t2"],
            },
            blocking=True,
        )


async def test_discovery_without_device(hass, mqtt_mock, caplog):
    """Test discovery, update and removal of notify service without device."""
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
    assert "Notify service ('notify', 'bla') updated has been processed" in caplog.text

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

    # test if a new service with same name fails to setup
    config1 = {
        "command_topic": "command-topic-config.yaml",
        "name": "test-setup1",
        "platform": "mqtt",
        "qos": "2",
    }
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {notify.DOMAIN: [config1]},
    )
    await hass.async_block_till_done()
    data = '{ "name": "test-setup1", "command_topic": "test_topic" }'
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/test-setup1/config", data
    )
    await hass.async_block_till_done()
    assert (
        "Notify service 'test_setup1' already exists, cannot register service"
        in caplog.text
    )
    await hass.services.async_call(
        notify.DOMAIN,
        "test_setup1",
        {
            notify.ATTR_TITLE: "Title",
            notify.ATTR_MESSAGE: "Message",
            notify.ATTR_TARGET: ["t2"],
        },
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic-config.yaml", "Message", 2, False
    )

    # Test with same discovery on new name
    data = '{ "name": "testa", "command_topic": "test_topic_a" }'
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/testa/config", data)
    await hass.async_block_till_done()
    assert "<Event service_registered[L]: domain=notify, service=testa>" in caplog.text

    data = '{ "name": "testb", "command_topic": "test_topic_b" }'
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/testb/config", data)
    await hass.async_block_till_done()
    assert "<Event service_registered[L]: domain=notify, service=testb>" in caplog.text

    # Try to update from new discovery of existing service test
    data = '{ "name": "testa", "command_topic": "test_topic_c" }'
    caplog.clear()
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/testc/config", data)
    await hass.async_block_till_done()
    assert (
        "Notify service 'testa' already exists, cannot register service" in caplog.text
    )

    # Try to update the same discovery to existing service test
    data = '{ "name": "testa", "command_topic": "test_topic_c" }'
    caplog.clear()
    async_fire_mqtt_message(hass, f"homeassistant/{notify.DOMAIN}/testb/config", data)
    await hass.async_block_till_done()
    assert (
        "Notify service 'testa' already exists, cannot register service" in caplog.text
    )


async def test_discovery_with_device_update(hass, mqtt_mock, caplog, device_reg):
    """Test discovery, update and removal of notify service with a device config."""

    # Initial setup
    data = '{ "command_topic": "test_topic", "name": "My notify service", "targets": ["target1", "target2"], "device":{"identifiers":["LCD_61236812_ADBA"], "name": "Test123" } }'
    service_name = "my_notify_service"
    await async_setup_notifify_service_with_auto_discovery(
        hass, mqtt_mock, caplog, device_reg, data, service_name
    )
    assert "<Event device_registry_updated[L]: action=create, device_id=" in caplog.text
    # Test device update
    data_device_update = '{ "command_topic": "test_topic", "name": "My notify service", "targets": ["target1", "target2"], "device":{"identifiers":["LCD_61236812_ADBA"], "name": "Name update" } }'
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/{service_name}/config", data_device_update
    )
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is not None
    device_id = device_entry.id
    assert device_id == device_entry.id
    assert device_entry.name == "Name update"

    # Test removal device from device registry using discovery
    caplog.clear()
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/{service_name}/config", "{}"
    )
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


async def test_discovery_with_device_removal(hass, mqtt_mock, caplog, device_reg):
    """Test discovery, update and removal of notify service with a device config."""

    # Initial setup
    data1 = '{ "command_topic": "test_topic", "name": "My notify service1", "targets": ["target1", "target2"], "device":{"identifiers":["LCD_61236812_ADBA"], "name": "Test123" } }'
    data2 = '{ "command_topic": "test_topic", "name": "My notify service2", "targets": ["target1", "target2"], "device":{"identifiers":["LCD_61236812_ADBA"], "name": "Test123" } }'
    service_name1 = "my_notify_service1"
    service_name2 = "my_notify_service2"
    await async_setup_notifify_service_with_auto_discovery(
        hass, mqtt_mock, caplog, device_reg, data1, service_name1
    )
    assert "<Event device_registry_updated[L]: action=create, device_id=" in caplog.text
    await async_setup_notifify_service_with_auto_discovery(
        hass, mqtt_mock, caplog, device_reg, data2, service_name2
    )
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is not None
    device_id = device_entry.id
    assert device_id == device_entry.id
    assert device_entry.name == "Test123"

    # Remove fist service
    caplog.clear()
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/{service_name1}/config", "{}"
    )
    await hass.async_block_till_done()
    assert (
        f"<Event service_removed[L]: domain=notify, service={service_name1}>"
        in caplog.text
    )
    assert (
        f"<Event service_removed[L]: domain=notify, service={service_name1}_target1>"
        in caplog.text
    )
    assert (
        f"<Event service_removed[L]: domain=notify, service={service_name1}_target2>"
        in caplog.text
    )
    assert (
        f"<Event device_registry_updated[L]: action=remove, device_id={device_id}>"
        not in caplog.text
    )
    caplog.clear()

    # The device should still be there
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is not None
    device_id = device_entry.id
    assert device_id == device_entry.id
    assert device_entry.name == "Test123"

    # Test removal device from device registry after removing second service
    async_fire_mqtt_message(
        hass, f"homeassistant/{notify.DOMAIN}/{service_name2}/config", "{}"
    )
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is None
    assert (
        f"<Event service_removed[L]: domain=notify, service={service_name2}>"
        in caplog.text
    )
    assert (
        f"<Event service_removed[L]: domain=notify, service={service_name2}_target1>"
        in caplog.text
    )
    assert (
        f"<Event service_removed[L]: domain=notify, service={service_name2}_target2>"
        in caplog.text
    )
    assert (
        f"<Event device_registry_updated[L]: action=remove, device_id={device_id}>"
        in caplog.text
    )
    caplog.clear()

    # Recreate the service and device
    await async_setup_notifify_service_with_auto_discovery(
        hass, mqtt_mock, caplog, device_reg, data1, service_name1
    )
    assert "<Event device_registry_updated[L]: action=create, device_id=" in caplog.text

    # Test removing the device from the device registry
    device_entry = device_reg.async_get_device({("mqtt", "LCD_61236812_ADBA")})
    assert device_entry is not None
    device_id = device_entry.id
    caplog.clear()
    device_reg.async_remove_device(device_id)
    await hass.async_block_till_done()
    assert (
        f"<Event service_removed[L]: domain=notify, service={service_name1}>"
        in caplog.text
    )
    assert (
        f"<Event service_removed[L]: domain=notify, service={service_name1}_target1>"
        in caplog.text
    )
    assert (
        f"<Event service_removed[L]: domain=notify, service={service_name1}_target2>"
        in caplog.text
    )
    assert (
        f"<Event device_registry_updated[L]: action=remove, device_id={device_id}>"
        in caplog.text
    )


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
