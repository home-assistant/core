"""Test the Liebherr coordinator."""

from unittest.mock import AsyncMock, MagicMock

from pyliebherrhomeapi import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
    LiebherrTimeoutError,
)
import pytest

from homeassistant.components.liebherr.coordinator import LiebherrCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock Liebherr client."""
    return MagicMock()


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain="liebherr")


@pytest.mark.parametrize(
    ("exception", "expected_error", "expected_match"),
    [
        (
            LiebherrAuthenticationError("Invalid API key"),
            ConfigEntryAuthFailed,
            "API key is no longer valid",
        ),
        (
            LiebherrTimeoutError("Timeout"),
            UpdateFailed,
            "Timeout communicating with device",
        ),
        (
            LiebherrConnectionError("Connection failed"),
            UpdateFailed,
            "Error communicating with device",
        ),
    ],
)
async def test_coordinator_update_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_error: type[Exception],
    expected_match: str,
) -> None:
    """Test coordinator handles update errors."""
    mock_client.get_device_state = AsyncMock(side_effect=exception)

    coordinator = LiebherrCoordinator(
        hass, mock_config_entry, mock_client, "test_device"
    )

    with pytest.raises(expected_error, match=expected_match):
        await coordinator._async_update_data()


@pytest.mark.parametrize(
    ("exception", "expected_error", "expected_match"),
    [
        (
            LiebherrAuthenticationError("Invalid API key"),
            ConfigEntryError,
            "Invalid API key",
        ),
        (
            LiebherrConnectionError("Connection failed"),
            ConfigEntryNotReady,
            "Failed to connect to device",
        ),
    ],
)
async def test_coordinator_setup_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_error: type[Exception],
    expected_match: str,
) -> None:
    """Test coordinator handles setup errors."""
    mock_client.get_device = AsyncMock(side_effect=exception)

    coordinator = LiebherrCoordinator(
        hass, mock_config_entry, mock_client, "test_device"
    )

    with pytest.raises(expected_error, match=expected_match):
        await coordinator._async_setup()
