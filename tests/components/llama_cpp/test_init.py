"""Tests for llama.cpp integration setup."""

from unittest.mock import AsyncMock, patch

import httpx2
import openai
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant


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
                response=httpx2.Response(
                    status_code=401,
                    request=httpx2.Request(method="GET", url="test"),
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


async def test_setup_entry_auth_failed_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_models_list: AsyncMock,
) -> None:
    """Test an authentication error during setup starts a reauth flow."""
    mock_models_list.side_effect = openai.AuthenticationError(
        message="Invalid API key",
        response=httpx2.Response(
            status_code=401,
            request=httpx2.Request(method="GET", url="test"),
        ),
        body=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
