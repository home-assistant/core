"""Test sentence triggers."""
import asyncio

import pytest

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    intent,
)
from homeassistant.setup import async_setup_component


@pytest.fixture
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})


async def test_register_trigger(hass: HomeAssistant, init_components):
    """Test registering/unregistering/matching a few trigger sentences."""
    triggered = asyncio.Event()

    def callback():
        triggered.set()

    unregister = await conversation.async_register_trigger_sentences(
        hass, ["It's party time", "It is time to party"], callback
    )

    result = await conversation.async_converse(hass, "Not the trigger", None, Context())
    assert result.response.response_type == intent.IntentResponseType.ERROR

    # Using different case and including punctuation
    sentences = ["it's party time!", "IT IS TIME TO PARTY."]
    for sentence in sentences:
        result = await conversation.async_converse(hass, sentence, None, Context())
        assert (
            result.response.response_type == intent.IntentResponseType.ACTION_DONE
        ), sentence

    unregister()

    # Should produce errors now
    for sentence in sentences:
        result = await conversation.async_converse(hass, sentence, None, Context())
        assert (
            result.response.response_type == intent.IntentResponseType.ERROR
        ), sentence
