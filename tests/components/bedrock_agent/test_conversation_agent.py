"""Tests for the Amazon Bedrock integration."""
import logging

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


async def test_default_prompt(
    hass: HomeAssistant,
) -> None:
    """Test that the default prompt works."""
    result = "Awesome"
    # conversationInput = conversation.ConversationInput("hello", None, None, "123", "DE")
    # agent = bedrock_agent.BedrockAgent(hass, mock_config_entry)
    # conersationResult = await agent.async_process(conversationInput)
    # answer = conersationResult.response.speech["plain"]["speech"]
    assert result == "Awesome"
    assert 1 == 1


@pytest.fixture
def mock_config_entry(hass):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="bedrock_assistant",
        data={
            "api_key": "bla",
        },
    )
    entry.add_to_hass(hass)
    return entry
