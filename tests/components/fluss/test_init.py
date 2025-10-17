"""Test script for Fluss+ integration initialization."""

from unittest.mock import AsyncMock, patch

from fluss_api import (
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)
import pytest

from homeassistant.components.fluss import async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from tests.common import MockConfigEntry


async def test_async_setup_entry_authentication_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that an authentication error during setup leads to SETUP_ERROR state."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.fluss.coordinator.FlussApiClient.async_get_devices",
        side_effect=FlussApiClientAuthenticationError("Invalid credentials"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [
        FlussApiClientCommunicationError("Network error"),
        FlussApiClientError("General error"),
    ],
    ids=["communication_error", "general_error"],
)
async def test_async_setup_entry_error(
    hass: HomeAssistant, mock_config_entry, error_type
) -> None:
    """Test that non-authentication errors during setup lead to SETUP_RETRY state."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.fluss.coordinator.FlussApiClient",
        side_effect=error_type,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.asyncio
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test the Fluss configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_api_client.async_get_devices.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
