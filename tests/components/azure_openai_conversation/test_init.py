"""Tests for the OpenAI integration."""

from unittest.mock import patch

from httpx import Response
from openai import APIConnectionError, AuthenticationError, BadRequestError
import pytest

from homeassistant.components.azure_openai_conversation.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (APIConnectionError(request=None), "Connection error"),
        (
            AuthenticationError(
                response=Response(status_code=None, request=""), body=None, message=None
            ),
            "Invalid API key",
        ),
        (
            BadRequestError(
                response=Response(status_code=None, request=""), body=None, message=None
            ),
            "openai_conversation integration not ready yet: None",
        ),
    ],
)
async def test_init_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    side_effect,
    error,
) -> None:
    """Test initialization errors."""
    with patch(
        "openai.resources.models.AsyncModels.list",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert error in caplog.text
