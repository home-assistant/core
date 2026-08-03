"""Tests for llama.cpp integration setup."""

from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and unloading llama.cpp entry."""
    with patch(
        "openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (
            openai.AuthenticationError(
                message="Invalid API key",
                response=httpx.Response(
                    status_code=401,
                    request=httpx.Request(method="GET", url="test"),
                ),
                body=None,
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            openai.APIConnectionError(request=None),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry failure handling."""
    with patch(
        "openai.resources.models.AsyncModels.list",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
