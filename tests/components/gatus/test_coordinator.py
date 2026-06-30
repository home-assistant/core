"""Tests for the Gatus DataUpdateCoordinator."""

from unittest.mock import AsyncMock, patch

from gatus_api.client import GatusClientError
import pytest

from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration


async def test_coordinator_successful_update(
    hass: HomeAssistant, mock_gatus_client: AsyncMock
) -> None:
    """Test a pristine successful data refresh cycle and URL sanitization."""
    mock_data = [{"key": "endpoint_1", "is_up": True}]
    config_entry = await setup_integration(hass, mock_gatus_client, mock_data)
    coordinator: GatusDataUpdateCoordinator = config_entry.runtime_data

    assert coordinator.url == "http://gatus.local"

    data = await coordinator._async_update_data()
    assert isinstance(data, list)
    assert data[0]["key"] == "endpoint_1"


async def test_coordinator_client_error(
    hass: HomeAssistant, mock_gatus_client: AsyncMock
) -> None:
    """Test that a library exception wraps cleanly into UpdateFailed."""
    config_entry = await setup_integration(hass, mock_gatus_client, [])
    coordinator: GatusDataUpdateCoordinator = config_entry.runtime_data

    with (
        patch.object(
            coordinator.client,
            "get_endpoints_statuses",
            AsyncMock(
                side_effect=GatusClientError(
                    "Error communicating with Gatus API: status code 500"
                )
            ),
        ),
        pytest.raises(UpdateFailed, match="Error communicating with Gatus API"),
    ):
        await coordinator._async_update_data()
