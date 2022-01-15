"""The tests for the MQTT button platform."""
import pytest

from homeassistant.components import notify
from homeassistant.components.mqtt import DOMAIN
from homeassistant.setup import async_setup_component

from .test_common import help_test_publishing_with_custom_encoding, help_test_reloadable

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


@pytest.mark.parametrize(
    "service,topic,parameters,payload,template",
    [
        (notify.SERVICE_NOTIFY, "command_topic", None, "PRESS", None),
    ],
)
async def test_publishing_with_custom_encoding(
    hass, mqtt_mock, caplog, service, topic, parameters, payload, template
):
    """Test publishing MQTT payload with different encoding."""
    domain = notify.DOMAIN
    config = DEFAULT_CONFIG[domain]

    await help_test_publishing_with_custom_encoding(
        hass,
        mqtt_mock,
        caplog,
        domain,
        config,
        service,
        topic,
        parameters,
        payload,
        template,
    )


async def test_reloadable(hass, mqtt_mock, caplog, tmp_path):
    """Test reloading the MQTT platform."""
    domain = notify.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable(hass, mqtt_mock, caplog, tmp_path, domain, config)
