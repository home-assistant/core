"""Test the Liebherr coordinator."""

from unittest.mock import AsyncMock, MagicMock

from pyliebherrhomeapi import LiebherrConnectionError, LiebherrTimeoutError
import pytest

from homeassistant.components.liebherr.coordinator import LiebherrCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_timeout_error(hass: HomeAssistant) -> None:
    """Test coordinator handles timeout errors."""
    mock_client = MagicMock()
    mock_client.get_device_state = AsyncMock(
        side_effect=LiebherrTimeoutError("Timeout")
    )

    mock_config_entry = MockConfigEntry(domain="liebherr")

    coordinator = LiebherrCoordinator(hass, mock_client, mock_config_entry)
    coordinator.device_ids = ["test_device"]

    with pytest.raises(UpdateFailed, match="Timeout communicating with API"):
        await coordinator._async_update_data()


async def test_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test coordinator handles connection errors."""
    mock_client = MagicMock()
    mock_client.get_device_state = AsyncMock(
        side_effect=LiebherrConnectionError("Connection failed")
    )

    mock_config_entry = MockConfigEntry(domain="liebherr")

    coordinator = LiebherrCoordinator(hass, mock_client, mock_config_entry)
    coordinator.device_ids = ["test_device"]

    with pytest.raises(UpdateFailed, match="Error communicating with API"):
        await coordinator._async_update_data()
