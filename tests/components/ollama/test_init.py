"""Tests for the Ollama integration."""

from unittest.mock import patch

from httpx import ConnectError
import pytest

from homeassistant.components import ollama
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ConnectError(message="Connect error"), "Connect error"),
        (RuntimeError("Runtime error"), "Runtime error"),
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
        "ollama.AsyncClient.list",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, ollama.DOMAIN, {})
        await hass.async_block_till_done()
        assert error in caplog.text
