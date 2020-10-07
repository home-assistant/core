"""The tests for the MQTT automation."""
from unittest import mock

import pytest

import homeassistant.components.automation as automation
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.setup import async_setup_component

from tests.common import async_fire_mqtt_message, async_mock_service, mock_component


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass, mqtt_mock):
    """Initialize components."""
    mock_component(hass, "group")


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
    assert len(calls) == 1
    assert 'mqtt - test-topic - { "hello": "world" } - world' == calls[0].data["some"]

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    async_fire_mqtt_message(hass, "test-topic", "test_payload")
    await hass.async_block_till_done()
    assert len(calls) == 1


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
    assert len(calls) == 1


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
    assert len(calls) == 0


async def test_encoding_default(hass, calls, mqtt_mock):
    """Test default encoding."""
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

    mqtt_mock.async_subscribe.assert_called_once_with(
        "test-topic", mock.ANY, 0, "utf-8"
    )


async def test_encoding_custom(hass, calls, mqtt_mock):
    """Test default encoding."""
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

    mqtt_mock.async_subscribe.assert_called_once_with("test-topic", mock.ANY, 0, None)
