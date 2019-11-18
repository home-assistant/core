"""
Tests for Rhasspy voice assistant integration.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
import asyncio
from unittest.mock import MagicMock, patch

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
    DEFAULT_INTENT_COMMANDS,
    DEFAULT_LANGUAGE,
)
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component


async def test_demo_commands(hass):
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

    with patch(
        "homeassistant.components.rhasspy.training.RhasspyClient"
    ) as make_mock_rhasspyclient:
        mock_rhasspyclient = make_mock_rhasspyclient.return_value

        mock_rhasspyclient.set_sentences = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.set_sentences.return_value.set_result("")

        mock_rhasspyclient.set_slots = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.set_slots.return_value.set_result("")

        mock_rhasspyclient.train = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.train.return_value.set_result("")

        await asyncio.gather(
            async_setup_component(hass, "light", config),
            async_setup_component(hass, "cover", config),
            async_setup_component(hass, "rhasspy", config),
        )

        # Wait for training to complete
        await train_event.wait()

        # Check that Rhasspy client was called
        assert mock_rhasspyclient.set_sentences.called
        assert mock_rhasspyclient.train.called

        sentences_by_intent = mock_rhasspyclient.set_sentences.call_args[0][0]

        # Ensure that commands for all default intents were generated
        for intent_name in DEFAULT_INTENT_COMMANDS[DEFAULT_LANGUAGE]:
            assert intent_name in sentences_by_intent

        # Spot check individual domains.
        # Check that all light/cover names show up in relevant sentences.
        for state in hass.states.async_all():
            if state.domain == "light":
                for intent_name in [intent.INTENT_TURN_ON, intent.INTENT_TURN_OFF]:
                    assert any(
                        state.name in s for s in sentences_by_intent[intent_name]
                    )
            elif state.domain == "cover":
                for intent_name in [INTENT_OPEN_COVER, INTENT_CLOSE_COVER]:
                    assert any(
                        state.name in s for s in sentences_by_intent[intent_name]
                    )


async def test_clean_name(hass):
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

    with patch(
        "homeassistant.components.rhasspy.training.RhasspyClient"
    ) as make_mock_rhasspyclient:
        mock_rhasspyclient = make_mock_rhasspyclient.return_value

        mock_rhasspyclient.set_sentences = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.set_sentences.return_value.set_result("")

        mock_rhasspyclient.set_slots = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.set_slots.return_value.set_result("")

        mock_rhasspyclient.train = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.train.return_value.set_result("")

        await asyncio.gather(
            async_setup_component(hass, "automation", config),
            async_setup_component(hass, "rhasspy", config),
        )

        # Wait for training to complete
        await train_event.wait()

        # Check that Rhasspy client was called
        assert mock_rhasspyclient.set_sentences.called
        assert mock_rhasspyclient.train.called

        sentences_by_intent = mock_rhasspyclient.set_sentences.call_args[0][0]

        # Check that intents were generated for automation
        assert INTENT_TRIGGER_AUTOMATION in sentences_by_intent
        assert INTENT_TRIGGER_AUTOMATION_LATER in sentences_by_intent

        # Verify that name was properly cleaned
        sentences = sentences_by_intent[INTENT_TRIGGER_AUTOMATION]
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

    with patch(
        "homeassistant.components.rhasspy.training.RhasspyClient"
    ) as make_mock_rhasspyclient:
        mock_rhasspyclient = make_mock_rhasspyclient.return_value

        mock_rhasspyclient.set_sentences = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.set_sentences.return_value.set_result("")

        mock_rhasspyclient.set_slots = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.set_slots.return_value.set_result("")

        mock_rhasspyclient.train = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.train.return_value.set_result("")

        await asyncio.gather(
            async_setup_component(hass, "light", config),
            async_setup_component(hass, "switch", config),
            async_setup_component(hass, "rhasspy", config),
        )

        # Wait for training to complete
        await train_event.wait()

        # Check that Rhasspy client was called
        assert mock_rhasspyclient.set_sentences.called
        assert mock_rhasspyclient.train.called

        sentences_by_intent = mock_rhasspyclient.set_sentences.call_args[0][0]

        # Verify that commands were only generated for HassTurnOn
        assert len(sentences_by_intent) == 1
        assert intent.INTENT_TURN_ON in sentences_by_intent

        # Check that only lights were included
        sentences = sentences_by_intent[intent.INTENT_TURN_ON]
        for state in hass.states.async_all():
            if state.domain == "light":
                assert any(state.name in s for s in sentences)
            elif state.domain == "switch":
                assert all(state.name not in s for s in sentences), sentences
