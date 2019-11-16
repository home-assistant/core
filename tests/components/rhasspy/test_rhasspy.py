"""
Tests for Rhasspy voice assistant integration.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
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


async def test_service_train(hass, aioclient_mock):
    """Test rhasspy.train service with sentences, slots, and custom words."""
    config = {
        "rhasspy": {
            CONF_MAKE_INTENT_COMMANDS: False,
            CONF_INTENT_COMMANDS: {
                "TestIntent": {KEY_COMMAND: "release the moogles $direction"}
            },
            CONF_CUSTOM_WORDS: {"moogles": "M UW G AH L Z"},
            CONF_SLOTS: {"direction": ["left", "right"]},
        }
    }

    assert await async_setup_component(hass, "rhasspy", config)
    provider = hass.data[DOMAIN]

    aioclient_mock.post(provider.sentences_url, status=200, data="")
    aioclient_mock.post(provider.custom_words_url, status=200, data="")
    aioclient_mock.post(provider.slots_url, status=200, data="")
    aioclient_mock.post(provider.train_url, status=200, data="")
    await hass.services.async_call(DOMAIN, SERVICE_TRAIN, {}, blocking=True)
    assert aioclient_mock.call_count == 4

    # Verify POST-ed data
    assert (
        aioclient_mock.mock_calls[0][2]
        == "[TestIntent]\nrelease the moogles $direction\n\n"
    )
    assert aioclient_mock.mock_calls[1][2] == "moogles M UW G AH L Z\n"
    slots = aioclient_mock.mock_calls[2][2]
    assert "direction" in slots
    assert sorted(slots["direction"]) == ["left", "right"]


async def test_conversation(hass, aioclient_mock):
    """Test conversation integration."""
    config = {"rhasspy": {CONF_REGISTER_CONVERSATION: True}, "conversation": {}}

    assert await async_setup_component(hass, "conversation", config)
    assert await async_setup_component(hass, "rhasspy", config)
    provider = hass.data[DOMAIN]

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

    aioclient_mock.post(
        provider.intent_url, status=200, json={"intent": {"name": test_intent}}
    )

    test_sentence = "this is a test"
    await hass.services.async_call(
        "conversation", "process", {"text": test_sentence}, blocking=True
    )

    # Verify call to Rhasspy API
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == test_sentence

    # Verify intent handled
    assert test_handler.handled
