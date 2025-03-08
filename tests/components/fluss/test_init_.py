"""Test Script for Fluss+ Initialisation."""

from unittest.mock import AsyncMock, patch

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)
import pytest

from homeassistant.components.fluss import DOMAIN, PLATFORMS, async_setup_entry
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady


@pytest.fixture
async def mock_hass():
    """Mock Hass Environment."""
    hass = AsyncMock(spec=HomeAssistant)
    hass.config_entries = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock()
    hass.data = {}
    return hass


@pytest.fixture
async def mock_entry():
    """Mock Fluss+ API entry."""
    entry = AsyncMock(spec=ConfigEntry)
    entry.data = {"api_key": "test_api_key"}
    entry.entry_id = "test_entry_id"
    entry.runtime_data = None  # Will be set during setup
    entry.state = ConfigEntryState.NOT_LOADED
    return entry


@pytest.mark.asyncio
async def test_async_setup_entry_authentication_error(mock_hass, mock_entry) -> None:
    """Test authentication failure raises ConfigEntryAuthFailed."""
    with (
        patch(
            "homeassistant.components.fluss.FlussApiClient",
            side_effect=FlussApiClientAuthenticationError,
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await async_setup_entry(mock_hass, mock_entry)


@pytest.mark.asyncio
async def test_async_setup_entry_communication_error(mock_hass, mock_entry) -> None:
    """Mock Communication Error."""
    with (
        patch(
            "homeassistant.components.fluss.FlussApiClient",
            side_effect=FlussApiClientCommunicationError,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(mock_hass, mock_entry)


@pytest.mark.asyncio
async def test_async_setup_entry_general_error(mock_hass, mock_entry) -> None:
    """Mock General Error."""
    with (
        patch(
            "homeassistant.components.fluss.FlussApiClient",
            side_effect=FlussApiClientError,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(mock_hass, mock_entry)


@pytest.mark.asyncio
async def test_async_setup_entry_success(mock_hass, mock_entry) -> None:
    """Test successful setup of a config entry."""
    mock_api_client = AsyncMock(spec=FlussApiClient)
    with patch(
        "homeassistant.components.fluss.FlussApiClient",
        return_value=mock_api_client,
    ) as mock_api_client_class:
        result = await async_setup_entry(mock_hass, mock_entry)

        # Verify FlussApiClient was initialized with correct parameters
        mock_api_client_class.assert_called_once_with(
            mock_entry.data["api_key"],
            "https://zgekzokxrl.execute-api.eu-west-1.amazonaws.com/v1/api/",
        )

        assert result is True
        assert mock_entry.runtime_data == mock_api_client
        mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_entry, PLATFORMS
        )
        # Verify that the API client is stored in hass.data
        assert mock_hass.data[DOMAIN][mock_entry.entry_id] == mock_api_client
