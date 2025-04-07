"""The tests for the MQTT automation."""

from unittest.mock import ANY

import pytest

from homeassistant.components import automation
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import HassJobType, HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import async_fire_mqtt_message, mock_component
from tests.typing import MqttMockHAClient, MqttMockHAClientGenerator


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(autouse=True)
async def setup_comp(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> MqttMockHAClient:
    """Initialize components."""
    mock_component(hass, "group")
    return await mqtt_mock_entry()


async def test_if_fires_on_topic_match(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
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
                        "some": "{{ trigger.platform }} - {{ trigger.topic }} - "
                        "{{ trigger.payload }} - {{ trigger.payload_json.hello }} - "
                        "{{ trigger.id }}"
                    },
                },
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", '{ "hello": "world" }')
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert (
        service_calls[0].data["some"]
        == 'mqtt - test-topic - { "hello": "world" } - world - 0'
    )

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    async_fire_mqtt_message(hass, "test-topic", "test_payload")
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_if_fires_on_topic_and_payload_match(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
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
    assert len(service_calls) == 1


async def test_if_fires_on_topic_and_payload_match2(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test if message is fired on topic and payload match.

    Make sure a payload which would render as a non string can still be matched.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic",
                    "payload": "0",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "0")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_templated_topic_and_payload_match(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test if message is fired on templated topic and payload match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic-{{ sqrt(16)|round }}",
                    "payload": '{{ "foo"|regex_replace("foo", "bar") }}',
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic-", "foo")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    async_fire_mqtt_message(hass, "test-topic-4", "foo")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    async_fire_mqtt_message(hass, "test-topic-4", "bar")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_payload_template(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test if message is fired on templated topic and payload match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic",
                    "payload": "hello",
                    "value_template": "{{ value_json.wanted_key }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "hello")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    async_fire_mqtt_message(hass, "test-topic", '{"unwanted_key":"hello"}')
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    async_fire_mqtt_message(hass, "test-topic", '{"wanted_key":"hello"}')
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_non_allowed_templates(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test non allowed function in template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic-{{ states() }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    assert (
        "Got error 'TemplateError: Use of 'states' is not supported in limited templates' when setting up triggers"
        in caplog.text
    )


async def test_if_not_fires_on_topic_but_no_payload_match(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
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
    assert len(service_calls) == 0


async def test_encoding_default(
    hass: HomeAssistant, service_calls: list[ServiceCall], setup_comp
) -> None:
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

    setup_comp.async_subscribe.assert_called_with(
        "test-topic", ANY, 0, "utf-8", HassJobType.Callback
    )


async def test_encoding_custom(
    hass: HomeAssistant, service_calls: list[ServiceCall], setup_comp
) -> None:
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

    setup_comp.async_subscribe.assert_called_with(
        "test-topic", ANY, 0, None, HassJobType.Callback
    )
