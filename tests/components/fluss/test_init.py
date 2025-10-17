"""Test script for Fluss+ integration initialization."""

from unittest.mock import patch

from fluss_api import (
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)
import pytest

from homeassistant.components.fluss import async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady


@pytest.mark.asyncio
async def test_async_setup_entry_authentication_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that an authentication error during setup raises ConfigEntryAuthFailed."""
    with (
        patch(
            "homeassistant.components.fluss.coordinator.FlussApiClient.async_get_devices",
            side_effect=FlussApiClientAuthenticationError("Invalid credentials"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await async_setup_entry(hass, mock_config_entry)


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
    """Test that non-authentication errors during setup raise ConfigEntryNotReady."""
    with (
        patch(
            "fluss_api.FlussApiClient",
            side_effect=error_type,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, mock_config_entry)
