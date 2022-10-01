"""Test intent_script component."""
from homeassistant.bootstrap import async_setup_component
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_intent_script(hass):
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


async def test_intent_script_wait_response(hass):
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


async def test_intent_script_falsy_reprompt(hass):
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
