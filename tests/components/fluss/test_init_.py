"""Test Script for Fluss+ Initialisation."""

from unittest.mock import AsyncMock, Mock, patch

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)
import pytest

from homeassistant.components.fluss import (
    DOMAIN,
    Platform,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.fixture
async def mock_hass():
    """Mock Hass Environment."""
    hass = AsyncMock(spec=HomeAssistant)
    hass.config_entries = Mock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=None)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.data = {DOMAIN: {}}
    return hass


@pytest.fixture
async def mock_entry():
    """Mock Fluss+ API entry."""
    entry = AsyncMock(spec=ConfigEntry)
    entry.data = {"api_key": "test_api_key"}
    entry.entry_id = "test_entry_id"
    entry.runtime_data = {}  # Adjusted to AsyncMock
    return entry


@pytest.mark.asyncio
async def test_async_setup_entry_success(mock_hass, mock_entry) -> None:
    """Mock Successful Entry."""
    mock_api_client = AsyncMock(spec=FlussApiClient)  # Adjusted to AsyncMock
    with patch(
        "homeassistant.components.fluss.FlussApiClient",
        return_value=mock_api_client,
    ):
        result = await async_setup_entry(mock_hass, mock_entry)
        assert result is True
        assert "api" in mock_entry.runtime_data
        mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_entry, [Platform.BUTTON]
        )


@pytest.mark.asyncio
async def test_async_setup_entry_authentication_error(mock_hass, mock_entry) -> None:
    """Mock Authentication Error."""
    with patch(
        "fluss_api.FlussApiClient.__init__",
        side_effect=FlussApiClientAuthenticationError,
    ):
        result = await async_setup_entry(mock_hass, mock_entry)
        assert result is False


@pytest.mark.asyncio
async def test_async_setup_entry_communication_error(mock_hass, mock_entry) -> None:
    """Mock Communication Error."""
    with patch(
        "fluss_api.FlussApiClient.__init__",
        side_effect=FlussApiClientCommunicationError,
    ):
        result = await async_setup_entry(mock_hass, mock_entry)
        assert result is False


@pytest.mark.asyncio
async def test_async_setup_entry_general_error(mock_hass, mock_entry) -> None:
    """Mock General Error."""
    with patch(
        "fluss_api.FlussApiClient.__init__",
        side_effect=FlussApiClientError,
    ):
        result = await async_setup_entry(mock_hass, mock_entry)
        assert result is False


@pytest.mark.asyncio
async def test_async_unload_entry_success(mock_hass, mock_entry) -> None:
    """Mock Successful Unloading."""
    # Ensure the entry exists in hass.data before unloading
    mock_hass.data[DOMAIN][mock_entry.entry_id] = {}
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new=AsyncMock(return_value=True),
    ):
        result = await async_unload_entry(mock_hass, mock_entry)
        assert result is True
        assert mock_entry.entry_id not in mock_hass.data[DOMAIN]
