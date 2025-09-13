"""Test the LM Studio integration initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import openai

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client_config_flow: AsyncMock,
) -> None:
    """Test successful setup of entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None


async def test_setup_entry_exception(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure when client creation fails."""
    mock_config_entry.add_to_hass(hass)

    # Remove required data to cause setup failure
    hass.config_entries.async_update_entry(mock_config_entry, data={})
    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert result is False


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client_config_flow: AsyncMock,
) -> None:
    """Test successful unload of entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_auth_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure with authentication error."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lmstudio.openai.AsyncOpenAI") as mock_client:
        # Create a mock client instance
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance

        # Create a mock for the chained call: client.with_options().models.list()
        # with_options() should return a synchronous client instance
        mock_with_options = AsyncMock()
        mock_models = AsyncMock()
        mock_models.list = AsyncMock(
            side_effect=openai.AuthenticationError(
                response=httpx.Response(
                    status_code=401,
                    request=httpx.Request(method="GET", url="http://localhost:1234"),
                ),
                body=None,
                message="Invalid API key",
            )
        )
        mock_with_options.models = mock_models
        # with_options should return immediately, not a coroutine
        mock_instance.with_options = lambda timeout: mock_with_options

        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure with connection error."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lmstudio.openai.AsyncOpenAI") as mock_client:
        # Create a mock client instance
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance

        # Create a mock for the chained call: client.with_options().models.list()
        # with_options() should return a synchronous client instance
        mock_with_options = AsyncMock()
        mock_models = AsyncMock()
        mock_models.list = AsyncMock(
            side_effect=openai.OpenAIError("Connection failed")
        )
        mock_with_options.models = mock_models
        # with_options should return immediately, not a coroutine
        mock_instance.with_options = lambda timeout: mock_with_options

        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
