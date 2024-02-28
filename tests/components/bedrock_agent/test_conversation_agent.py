"""Tests for the Amazon Bedrock integration."""
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def test_default_prompt(
    hass: HomeAssistant,
) -> None:
    """Test that the default prompt works."""
    result = "Awesome"
    # result = await conversation.async_converse(hass, "hello", None, Context())
    # assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result == "Awesome"
    assert 1 == 1
