"""Test Script for Fluss+ Initialisation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)
import pytest

from homeassistant.components.fluss import PLATFORMS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady


@pytest.mark.parametrize(
    "side_effect, expected_exception",
    [
        (FlussApiClientAuthenticationError, ConfigEntryAuthFailed),
        (FlussApiClientCommunicationError, ConfigEntryNotReady),
        (FlussApiClientError, ConfigEntryNotReady),
    ],
)
async def test_async_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    side_effect: Exception,
    expected_exception: type[Exception],
) -> None:
    """Test setup errors."""
    with (
        patch("fluss_api.FlussApiClient", side_effect=side_effect),
        pytest.raises(expected_exception),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_api_client: FlussApiClient,
) -> None:
    """Test successful setup."""
    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.LOADED
        hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_config_entry, PLATFORMS
        )


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_api_client: FlussApiClient,
) -> None:
    """Test unloading entry."""
    # Set up the config entry first to ensure it's in LOADED state
    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    # Test unloading
    with patch("homeassistant.components.fluss.async_unload_platforms", return_value=True):
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.asyncio
async def test_platforms_forwarded(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_api_client: FlussApiClient,
) -> None:
    """Test platforms are forwarded correctly."""
    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.LOADED
        hass.config_entries.async_forward_entry_setups.assert_called_with(
            mock_config_entry, [Platform.BUTTON]
        )