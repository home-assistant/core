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
from homeassistant.components.fluss.button import FlussDataUpdateCoordinator
from homeassistant.components.fluss.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fluss Integration",
        data={CONF_API_KEY: "test_api_key"},
        unique_id="test_api_key",
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def test_async_setup_entry_authentication_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test authentication failure raises ConfigEntryAuthFailed."""
    with (
        patch(
            "homeassistant.components.fluss.coordinator.FlussApiClient.async_get_devices",
            side_effect=FlussApiClientAuthenticationError("Invalid credentials"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_setup_entry_communication_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test communication error raises ConfigEntryNotReady."""
    with (
        patch(
            "fluss_api.FlussApiClient",
            side_effect=FlussApiClientCommunicationError,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_setup_entry_general_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test general error raises ConfigEntryNotReady."""
    with (
        patch(
            "fluss_api.FlussApiClient",
            side_effect=FlussApiClientCommunicationError,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, mock_config_entry)
