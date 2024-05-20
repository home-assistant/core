"""Test intent_script component."""

from unittest.mock import patch

from homeassistant import config as hass_config
from homeassistant.bootstrap import async_setup_component
from homeassistant.components.intent_script import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service, get_fixture_path


async def test_intent_script(hass: HomeAssistant) -> None:
    """Test intent scripts work."""
    calls = async_mock_service(hass, "test", "service")

    await async_setup_component(
        hass,
        "intent_script",
        {
            "intent_script": {
                "HelloWorld": {
                    "action": {
                        "service": "test.service",
                        "data_template": {"hello": "{{ name }}"},
                    },
                    "card": {
                        "title": "Hello {{ name }}",
                        "content": "Content for {{ name }}",
                    },
                    "speech": {"text": "Good morning {{ name }}"},
                }
            }
        },
    )

    response = await intent.async_handle(
        hass, "test", "HelloWorld", {"name": {"value": "Paulus"}}
    )

    assert len(calls) == 1
    assert calls[0].data["hello"] == "Paulus"

    assert response.speech["plain"]["speech"] == "Good morning Paulus"

    assert not (response.reprompt)

    assert response.card["simple"]["title"] == "Hello Paulus"
    assert response.card["simple"]["content"] == "Content for Paulus"


async def test_intent_script_wait_response(hass: HomeAssistant) -> None:
    """Test intent scripts work."""
    calls = async_mock_service(hass, "test", "service")

    await async_setup_component(
        hass,
        "intent_script",
        {
            "intent_script": {
                "HelloWorldWaitResponse": {
                    "action": {
                        "service": "test.service",
                        "data_template": {"hello": "{{ name }}"},
                    },
                    "card": {
                        "title": "Hello {{ name }}",
                        "content": "Content for {{ name }}",
                    },
                    "speech": {"text": "Good morning {{ name }}"},
                    "reprompt": {
                        "text": "I didn't hear you, {{ name }}... I said good morning!"
                    },
                }
            }
        },
    )

    response = await intent.async_handle(
        hass, "test", "HelloWorldWaitResponse", {"name": {"value": "Paulus"}}
    )

    assert len(calls) == 1
    assert calls[0].data["hello"] == "Paulus"

    assert response.speech["plain"]["speech"] == "Good morning Paulus"

    assert (
        response.reprompt["plain"]["reprompt"]
        == "I didn't hear you, Paulus... I said good morning!"
    )

    assert response.card["simple"]["title"] == "Hello Paulus"
    assert response.card["simple"]["content"] == "Content for Paulus"


async def test_intent_script_service_response(hass: HomeAssistant) -> None:
    """Test intent scripts work."""
    calls = async_mock_service(
        hass, "test", "service", response={"some_key": "some value"}
    )

    await async_setup_component(
        hass,
        "intent_script",
        {
            "intent_script": {
                "HelloWorldServiceResponse": {
                    "action": [
                        {"service": "test.service", "response_variable": "result"},
                        {"stop": "", "response_variable": "result"},
                    ],
                    "speech": {
                        "text": "The service returned {{ action_response.some_key }}"
                    },
                }
            }
        },
    )

    response = await intent.async_handle(hass, "test", "HelloWorldServiceResponse")

    assert len(calls) == 1
    assert calls[0].return_response

    assert response.speech["plain"]["speech"] == "The service returned some value"


async def test_intent_script_falsy_reprompt(hass: HomeAssistant) -> None:
    """Test intent scripts work."""
    calls = async_mock_service(hass, "test", "service")

    await async_setup_component(
        hass,
        "intent_script",
        {
            "intent_script": {
                "HelloWorld": {
                    "action": {
                        "service": "test.service",
                        "data_template": {"hello": "{{ name }}"},
                    },
                    "card": {
                        "title": "Hello {{ name }}",
                        "content": "Content for {{ name }}",
                    },
                    "speech": {
                        "type": "ssml",
                        "text": '<speak><amazon:effect name="whispered">Good morning {{ name }}</amazon:effect></speak>',
                    },
                    "reprompt": {"text": "{{ null }}"},
                }
            }
        },
    )

    response = await intent.async_handle(
        hass, "test", "HelloWorld", {"name": {"value": "Paulus"}}
    )

    assert len(calls) == 1
    assert calls[0].data["hello"] == "Paulus"

    assert (
        response.speech["ssml"]["speech"]
        == '<speak><amazon:effect name="whispered">Good morning Paulus</amazon:effect></speak>'
    )

    assert not (response.reprompt)

    assert response.card["simple"]["title"] == "Hello Paulus"
    assert response.card["simple"]["content"] == "Content for Paulus"


async def test_reload(hass: HomeAssistant) -> None:
    """Verify we can reload intent config."""

    config = {"intent_script": {"NewIntent1": {"speech": {"text": "HelloWorld123"}}}}

    await async_setup_component(hass, "intent_script", config)
    await hass.async_block_till_done()

    intents = hass.data.get(intent.DATA_KEY)

    assert len(intents) == 1
    assert intents.get("NewIntent1")

    yaml_path = get_fixture_path("configuration.yaml", "intent_script")

    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(intents) == 1

    assert intents.get("NewIntent1") is None
    assert intents.get("NewIntent2")

    yaml_path = get_fixture_path("configuration_no_entry.yaml", "intent_script")

    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    # absence of intent_script from the configuration.yaml should delete all intents.
    assert len(intents) == 0
    assert intents.get("NewIntent1") is None
    assert intents.get("NewIntent2") is None
