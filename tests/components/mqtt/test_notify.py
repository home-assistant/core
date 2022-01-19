"""The tests for the MQTT button platform."""
import copy

from homeassistant.components import notify, siren
from homeassistant.components.mqtt import DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.discovery import async_load_platform

from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {"message_command_topic": "message-command-topic"}


async def async_register_service(hass, config):
    """Notify service setup."""
    hass.async_create_task(
        async_load_platform(hass, notify.DOMAIN, DOMAIN, config, config)
    )
    await hass.async_block_till_done()


async def test_platform_setup(hass, mqtt_mock, caplog):
    """Test the platform setup."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["siren_entity"] = {}
    await async_register_service(hass, config)
    assert (
        "Object {} is not a valid MqttSiren entity for dictionary value @ data['siren_entity']"
        in caplog.text
    )

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["name"] = "setup1"
    await async_register_service(hass, config)
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_setup1>"
        in caplog.text
    )
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["name"] = "setup2"
    await async_register_service(hass, config)
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_setup2>"
        in caplog.text
    )


async def test_sending_mqtt_commands(hass, mqtt_mock, caplog):
    """Test the sending MQTT commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["name"] = "setup1"
    await async_register_service(hass, config)
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_setup1>"
        in caplog.text
    )
    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}_setup1",
        {notify.ATTR_TITLE: "Title", notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "message-command-topic", "Message", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["name"] = "setup2"
    config["message_command_topic"] = "message-command-topic2"
    await async_register_service(hass, config)
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_setup2>"
        in caplog.text
    )

    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}",
        {
            notify.ATTR_TITLE: "Title",
            notify.ATTR_MESSAGE: "Message",
            notify.ATTR_TARGET: ["setup1"],
        },
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "message-command-topic", "Message", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}",
        {
            notify.ATTR_TITLE: "Title",
            notify.ATTR_MESSAGE: "Message",
            notify.ATTR_TARGET: ["setup1", "setup2"],
        },
        blocking=True,
    )
    mqtt_mock.async_publish.assert_any_call(
        "message-command-topic", "Message", 0, False
    )
    mqtt_mock.async_publish.assert_any_call(
        "message-command-topic2", "Message", 0, False
    )
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.reset_mock()


async def test_discovery(hass, mqtt_mock, caplog):
    """Test discovery, update and removal of notify service."""
    data = '{ "unique_id": "veryunique", "target": "test", "command_topic": "test_topic", "message_command_topic": "message_test_topic" }'
    data_update = '{ "unique_id": "veryunique", "target": "new name", "command_topic": "test_topic_update", "message_command_topic": "message_test_topic", "name": "New name", "message_command_template": "{{title}},{{message}},{{param1}}" }'

    async_fire_mqtt_message(hass, f"homeassistant/{siren.DOMAIN}/bla/config", data)
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

    mqtt_mock.async_publish.assert_called_once_with(
        "message_test_topic", "Message", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    async_fire_mqtt_message(
        hass, f"homeassistant/{siren.DOMAIN}/bla/config", data_update
    )
    await hass.async_block_till_done()

    ent_registry = er.async_get(hass)
    assert ent_registry.async_get_entity_id(siren.DOMAIN, DOMAIN, "veryunique")

    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_new_name>"
        in caplog.text
    )
    assert "<Event service_removed[L]: domain=notify, service=mqtt_test>" in caplog.text

    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}_new_name",
        {
            notify.ATTR_TITLE: "Title",
            notify.ATTR_MESSAGE: "Message",
            notify.ATTR_DATA: {"param1": "val1"},
        },
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "message_test_topic", "Title,Message,val1", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}",
        {
            notify.ATTR_TITLE: "Title",
            notify.ATTR_MESSAGE: "Message",
            notify.ATTR_DATA: {"param1": "val1"},
            notify.ATTR_TARGET: ["new_name", "invalid"],
        },
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "message_test_topic", "Title,Message,val1", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    assert hass.states.get("siren.mqtt_siren") is not None

    async_fire_mqtt_message(hass, f"homeassistant/{siren.DOMAIN}/bla/config", "")
    await hass.async_block_till_done()

    assert "Removing component: siren.mqtt_siren" in caplog.text

    assert hass.states.get("siren.mqtt_siren") is None
    assert (
        "<Event service_removed[L]: domain=notify, service=mqtt_new_name>"
        in caplog.text
    )


async def test_publishing_with_custom_encoding(hass, mqtt_mock, caplog):
    """Test publishing MQTT payload with different encoding."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["encoding"] = "utf-16"

    await async_register_service(hass, config)
    assert (
        "<Event service_registered[L]: domain=notify, service=mqtt_message_command_topic>"
        in caplog.text
    )
    await hass.services.async_call(
        notify.DOMAIN,
        f"{DOMAIN}_message_command_topic",
        {notify.ATTR_MESSAGE: "Message"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "message-command-topic",
        b"\xff\xfeM\x00e\x00s\x00s\x00a\x00g\x00e\x00",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
