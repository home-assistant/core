"""
Tests for Rhasspy voice assistant integration.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
import asyncio
import configparser
from urllib.parse import urljoin

from homeassistant.components.cover import INTENT_CLOSE_COVER, INTENT_OPEN_COVER
from homeassistant.components.rhasspy.const import (
    CONF_INTENT_FILTERS,
    CONF_MAKE_INTENT_COMMANDS,
    CONF_SHOPPING_LIST_ITEMS,
    EVENT_RHASSPY_TRAINED,
    INTENT_TRIGGER_AUTOMATION,
    INTENT_TRIGGER_AUTOMATION_LATER,
    KEY_DOMAINS,
    KEY_INCLUDE,
)
from homeassistant.components.rhasspy.default_settings import (
    DEFAULT_API_URL,
    DEFAULT_INTENT_COMMANDS,
    DEFAULT_LANGUAGE,
)
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component


async def test_demo_commands(hass, aioclient_mock):
    """Test automatically generated commands for demo platforms."""
    config = {
        "rhasspy": {
            CONF_MAKE_INTENT_COMMANDS: True,
            CONF_SHOPPING_LIST_ITEMS: ["apples", "bananas"],
        },
        "light": {"platform": "demo"},
        "cover": {"platform": "demo"},
    }

    # Register listener
    train_event = asyncio.Event()
    hass.bus.async_listen_once(EVENT_RHASSPY_TRAINED, lambda e: train_event.set())

    aioclient_mock.post(urljoin(DEFAULT_API_URL, "sentences"), status=200, data="")
    aioclient_mock.post(urljoin(DEFAULT_API_URL, "slots"), status=200, data="")
    aioclient_mock.post(urljoin(DEFAULT_API_URL, "train"), status=200, data="")

    await asyncio.gather(
        async_setup_component(hass, "light", config),
        async_setup_component(hass, "cover", config),
        async_setup_component(hass, "rhasspy", config),
    )

    # Wait for training to complete
    await train_event.wait()

    # Check that training URLs were POST-ed to
    assert aioclient_mock.call_count == 3

    # Verify POST-ed sentences (first call)
    parser = configparser.ConfigParser(
        allow_no_value=True, strict=False, delimiters=["="]
    )

    parser.optionxform = str  # case sensitive
    parser.read_string(aioclient_mock.mock_calls[0][2])

    # Ensure that commands for all default intents were generated
    for intent_name in DEFAULT_INTENT_COMMANDS[DEFAULT_LANGUAGE]:
        assert intent_name in parser.sections()

    sentences_by_intent = {
        intent_name: [k for k, v in parser[intent_name].items() if v is None]
        for intent_name in parser.sections()
    }

    # Spot check individual domains.
    # Check that all light/cover names show up in relevant sentences.
    for state in hass.states.async_all():
        if state.domain == "light":
            for intent_name in [intent.INTENT_TURN_ON, intent.INTENT_TURN_OFF]:
                assert any(state.name in s for s in sentences_by_intent[intent_name])
        elif state.domain == "cover":
            for intent_name in [INTENT_OPEN_COVER, INTENT_CLOSE_COVER]:
                assert any(state.name in s for s in sentences_by_intent[intent_name])


async def test_clean_name(hass, aioclient_mock):
    """Test entity name cleaning in automatically generated commands."""
    config = {
        "rhasspy": {CONF_MAKE_INTENT_COMMANDS: True},
        "automation": [
            {
                "alias": "Order_66",
                "trigger": {"platform": "event", "event_type": "FakeEvent1"},
                "action": {"service": "notify.notify", "data": {"message": "test"}},
            }
        ],
    }

    # Register listener
    train_event = asyncio.Event()
    hass.bus.async_listen_once(EVENT_RHASSPY_TRAINED, lambda e: train_event.set())

    aioclient_mock.post(urljoin(DEFAULT_API_URL, "sentences"), status=200, data="")
    aioclient_mock.post(urljoin(DEFAULT_API_URL, "slots"), status=200, data="")
    aioclient_mock.post(urljoin(DEFAULT_API_URL, "train"), status=200, data="")

    await asyncio.gather(
        async_setup_component(hass, "automation", config),
        async_setup_component(hass, "rhasspy", config),
    )

    # Wait for training to complete
    await train_event.wait()

    # Check that training URLs were POST-ed to
    assert aioclient_mock.call_count == 3

    # # Verify POST-ed sentences (first call)
    parser = configparser.ConfigParser(
        allow_no_value=True, strict=False, delimiters=["="]
    )

    parser.optionxform = str  # case sensitive
    parser.read_string(aioclient_mock.mock_calls[0][2])

    # Check that intents were generated for automation
    assert INTENT_TRIGGER_AUTOMATION in parser.sections()
    assert INTENT_TRIGGER_AUTOMATION_LATER in parser.sections()

    # Verify that name was properly cleaned
    sentences = [k for k, v in parser[INTENT_TRIGGER_AUTOMATION].items() if v is None]
    assert any("Order sixty six" in s for s in sentences)


async def test_include_domains(hass, aioclient_mock):
    """Test domain include in automatically generated commands."""
    config = {
        "rhasspy": {
            CONF_MAKE_INTENT_COMMANDS: {KEY_INCLUDE: [intent.INTENT_TURN_ON]},
            CONF_INTENT_FILTERS: {
                intent.INTENT_TURN_ON: {KEY_INCLUDE: {KEY_DOMAINS: ["light"]}}
            },
        },
        "light": {"platform": "demo"},
        "switch": {"platform": "demo"},
    }

    # Register listener
    train_event = asyncio.Event()
    hass.bus.async_listen_once(EVENT_RHASSPY_TRAINED, lambda e: train_event.set())

    aioclient_mock.post(urljoin(DEFAULT_API_URL, "sentences"), status=200, data="")
    aioclient_mock.post(urljoin(DEFAULT_API_URL, "slots"), status=200, data="")
    aioclient_mock.post(urljoin(DEFAULT_API_URL, "train"), status=200, data="")

    await asyncio.gather(
        async_setup_component(hass, "light", config),
        async_setup_component(hass, "switch", config),
        async_setup_component(hass, "rhasspy", config),
    )

    # Wait for training to complete
    await train_event.wait()

    # Check that training URLs were POST-ed to
    assert aioclient_mock.call_count == 3

    # Verify POST-ed sentences (first call)
    parser = configparser.ConfigParser(
        allow_no_value=True, strict=False, delimiters=["="]
    )

    parser.optionxform = str  # case sensitive
    parser.read_string(aioclient_mock.mock_calls[0][2])

    # Verify that commands were only generated for HassTurnOn
    assert len(parser.sections()) == 1
    assert intent.INTENT_TURN_ON in parser.sections()

    # Check that only lights were included
    sentences = [k for k, v in parser[intent.INTENT_TURN_ON].items() if v is None]
    for state in hass.states.async_all():
        if state.domain == "light":
            assert any(state.name in s for s in sentences)
        elif state.domain == "switch":
            assert all(state.name not in s for s in sentences), sentences
