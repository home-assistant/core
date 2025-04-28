"""Tests for the Anthropic integration."""

from unittest.mock import patch

from anthropic import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
)
from httpx import URL, Request, Response
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (APIConnectionError(request=None), "Connection error"),
        (APITimeoutError(request=None), "Request timed out"),
        (
            BadRequestError(
                message="Your credit balance is too low to access the Claude API. Please go to Plans & Billing to upgrade or purchase credits.",
                response=Response(
                    status_code=400,
                    request=Request(method="POST", url=URL()),
                ),
                body={"type": "error", "error": {"type": "invalid_request_error"}},
            ),
            "anthropic integration not ready yet: Your credit balance is too low to access the Claude API",
        ),
        (
            AuthenticationError(
                message="invalid x-api-key",
                response=Response(
                    status_code=401,
                    request=Request(method="POST", url=URL()),
                ),
                body={"type": "error", "error": {"type": "authentication_error"}},
            ),
            "Invalid API key",
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
        "anthropic.resources.models.AsyncModels.retrieve",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, "anthropic", {})
        await hass.async_block_till_done()
        assert error in caplog.text
