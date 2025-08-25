"""Test Script for Fluss+ Initialisation."""

from unittest.mock import AsyncMock, patch

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)
import pytest

from homeassistant.components.fluss import PLATFORMS, async_setup_entry
from homeassistant.config_entries import ConfigEntryState, MockConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady


@pytest.fixture
async def mock_entry():
    """Mock Fluss+ API entry."""
    entry = MockConfigEntry(
        domain="fluss",
        data={"api_key": "test_api_key"},
        entry_id="test_entry_id",
    )
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
    """Test communication error raises ConfigEntryNotReady."""
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
    """Test general error raises ConfigEntryNotReady."""
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

        # Verify FlussApiClient was initialized with the correct API key and URL
        mock_api_client_class.assert_called_once_with(
            mock_entry.data["api_key"],
            "https://zgekzokxrl.execute-api.eu-west-1.amazonaws.com/v1/api/",
        )

        assert result is True
        # Verify that the API client is stored in the entry's runtime data
        assert mock_entry.runtime_data == mock_api_client
        mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_entry, PLATFORMS
        )