"""Test Script for Fluss+ Initialisation."""

from unittest.mock import AsyncMock, patch

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)
import pytest

from homeassistant.components.fluss import (
    DOMAIN,
    PLATFORMS,
    Platform,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant


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
    entry.runtime_data = {}
    entry.state = ConfigEntryState.NOT_LOADED
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
    mock_hass.data[DOMAIN] = {mock_entry.entry_id: {"platforms": PLATFORMS}}
    mock_hass.config_entries.async_unload_platforms.return_value = True

    result = await async_unload_entry(mock_hass, mock_entry)

    assert result is True
    assert DOMAIN not in mock_hass.data
    mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
        mock_entry, PLATFORMS
    )


@pytest.mark.asyncio
async def test_async_unload_entry_not_loaded(mock_hass, mock_entry) -> None:
    """Test unloading when entry is not loaded."""
    mock_hass.data[DOMAIN] = {}

    result = await async_unload_entry(mock_hass, mock_entry)
    assert result is False
    assert DOMAIN in mock_hass.data
    mock_hass.config_entries.async_unload_platforms.assert_not_called()


@pytest.mark.asyncio
async def test_async_unload_entry_failure(mock_hass, mock_entry) -> None:
    """Test unloading when platforms fail to unload."""
    mock_hass.data[DOMAIN] = {mock_entry.entry_id: {"platforms": PLATFORMS}}
    mock_hass.config_entries.async_unload_platforms.return_value = False

    result = await async_unload_entry(mock_hass, mock_entry)

    assert result is False
    assert DOMAIN in mock_hass.data
    assert mock_entry.entry_id in mock_hass.data[DOMAIN]
    mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
        mock_entry, PLATFORMS
    )
