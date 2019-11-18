"""
Tests for Rhasspy voice assistant integration.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
import asyncio
from unittest.mock import MagicMock, patch

from homeassistant.components.rhasspy import RhasspyProvider
from homeassistant.components.rhasspy.const import (
    CONF_CUSTOM_WORDS,
    CONF_INTENT_COMMANDS,
    CONF_MAKE_INTENT_COMMANDS,
    CONF_REGISTER_CONVERSATION,
    CONF_SLOTS,
    DOMAIN,
    KEY_COMMAND,
    SERVICE_TRAIN,
)
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component


async def test_setup_component(hass):
    """Test setup component."""
    config = {"rhasspy": {}}

    assert await async_setup_component(hass, "rhasspy", config)
    assert hass.services.has_service(DOMAIN, SERVICE_TRAIN)

    # Verify that provider is available
    provider = hass.data.get(DOMAIN)
    assert isinstance(provider, RhasspyProvider)


async def test_service_train(hass):
    """Test rhasspy.train service with sentences, slots, and custom words."""
    intent_commands = {"TestIntent": {KEY_COMMAND: "release the moogles $direction"}}
    custom_words = {"moogles": "M UW G AH L Z"}
    slots = {"direction": ["left", "right"]}

    config = {
        "rhasspy": {
            CONF_MAKE_INTENT_COMMANDS: False,
            CONF_INTENT_COMMANDS: intent_commands,
            CONF_CUSTOM_WORDS: custom_words,
            CONF_SLOTS: slots,
        }
    }

    assert await async_setup_component(hass, "rhasspy", config)

    with patch(
        "homeassistant.components.rhasspy.training.RhasspyClient"
    ) as make_mock_rhasspyclient:
        mock_rhasspyclient = make_mock_rhasspyclient.return_value

        mock_rhasspyclient.set_sentences = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.set_sentences.return_value.set_result("")

        mock_rhasspyclient.set_custom_words = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.set_custom_words.return_value.set_result("")

        mock_rhasspyclient.set_slots = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.set_slots.return_value.set_result("")

        mock_rhasspyclient.train = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.train.return_value.set_result("")

        await hass.services.async_call(DOMAIN, SERVICE_TRAIN, {}, blocking=True)

        # Verify data
        assert mock_rhasspyclient.set_sentences.call_args[0][0] == {
            "TestIntent": ["release the moogles $direction"]
        }
        assert mock_rhasspyclient.set_custom_words.call_args[0][0] == custom_words
        assert (
            mock_rhasspyclient.set_slots.call_args[0][0]["direction"]
            == slots["direction"]
        )
        assert mock_rhasspyclient.train.called


async def test_conversation(hass):
    """Test conversation integration."""
    config = {"rhasspy": {CONF_REGISTER_CONVERSATION: True}, "conversation": {}}

    assert await async_setup_component(hass, "conversation", config)
    assert await async_setup_component(hass, "rhasspy", config)

    test_intent = "TestIntent"

    # Register handler for test intent
    class TestIntent(intent.IntentHandler):
        """Handle TestIntent by setting a boolean."""

        intent_type = test_intent

        def __init__(self):
            self.handled = True

        async def async_handle(self, intent_obj):
            self.handled = True

    test_handler = TestIntent()
    intent.async_register(hass, test_handler)

    # Test conversation/process pass-through to rhasspy
    assert hass.services.has_service("conversation", "process")

    with patch(
        "homeassistant.components.rhasspy.conversation.RhasspyClient"
    ) as make_mock_rhasspyclient:
        mock_rhasspyclient = make_mock_rhasspyclient.return_value

        mock_rhasspyclient.text_to_intent = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.text_to_intent.return_value.set_result(
            {"intent": {"name": test_intent}}
        )

        test_sentence = "this is a test"
        await hass.services.async_call(
            "conversation", "process", {"text": test_sentence}, blocking=True
        )

        # Verify call to Rhasspy
        assert mock_rhasspyclient.text_to_intent.call_args[0][0] == test_sentence

        # Verify intent handled
        assert test_handler.handled
