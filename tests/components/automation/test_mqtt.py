"""The tests for the MQTT automation."""
from unittest import mock

import pytest

import homeassistant.components.automation as automation
from homeassistant.setup import async_setup_component

from tests.common import (
    async_fire_mqtt_message,
    async_mock_mqtt_component,
    async_mock_service,
    mock_component,
)
from tests.components.automation import common


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")
    hass.loop.run_until_complete(async_mock_mqtt_component(hass))


async def test_if_fires_on_topic_match(hass, calls):
    """Test if message is fired on topic match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "mqtt", "topic": "test-topic"},
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.platform }} - {{ trigger.topic }}"
                        " - {{ trigger.payload }} - "
                        "{{ trigger.payload_json.hello }}"
                    },
                },
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", '{ "hello": "world" }')
    await hass.async_block_till_done()
    assert 1 == len(calls)
    assert 'mqtt - test-topic - { "hello": "world" } - world' == calls[0].data["some"]

    await common.async_turn_off(hass)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "test-topic", "test_payload")
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_on_topic_and_payload_match(hass, calls):
    """Test if message is fired on topic and payload match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic",
                    "payload": "hello",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "hello")
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_not_fires_on_topic_but_no_payload_match(hass, calls):
    """Test if message is not fired on topic but no payload."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic",
                    "payload": "hello",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "no-hello")
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_encoding_default(hass, calls):
    """Test default encoding."""
    mock_mqtt = await async_mock_mqtt_component(hass)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "mqtt", "topic": "test-topic"},
                "action": {"service": "test.automation"},
            }
        },
    )

    mock_mqtt.async_subscribe.assert_called_once_with(
        "test-topic", mock.ANY, 0, "utf-8"
    )


async def test_encoding_custom(hass, calls):
    """Test default encoding."""
    mock_mqtt = await async_mock_mqtt_component(hass)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "mqtt", "topic": "test-topic", "encoding": ""},
                "action": {"service": "test.automation"},
            }
        },
    )

    mock_mqtt.async_subscribe.assert_called_once_with("test-topic", mock.ANY, 0, None)
