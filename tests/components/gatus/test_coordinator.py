"""Tests for the Gatus DataUpdateCoordinator."""

from unittest.mock import AsyncMock

from gatus_api.client import GatusClientError

from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_coordinator_successful_update(
    hass: HomeAssistant, mock_gatus_client: AsyncMock
) -> None:
    """Test a pristine successful data refresh cycle and URL sanitization."""
    mock_data = [{"key": "endpoint_1", "is_up": True}]
    config_entry = await setup_integration(hass, mock_gatus_client, mock_data)
    coordinator: GatusDataUpdateCoordinator = config_entry.runtime_data

    assert coordinator.url == "http://gatus.local:80"

    assert coordinator.last_update_success is True
    assert isinstance(coordinator.data, list)
    assert coordinator.data[0]["key"] == "endpoint_1"


async def test_coordinator_client_error(
    hass: HomeAssistant, mock_gatus_client: AsyncMock
) -> None:
    """Test that a library exception cleanly marks a runtime update as failed."""
    mock_data = [{"key": "endpoint_1", "is_up": True}]
    config_entry = await setup_integration(hass, mock_gatus_client, mock_data)
    coordinator: GatusDataUpdateCoordinator = config_entry.runtime_data

    assert coordinator.last_update_success is True

    mock_gatus_client.get_endpoints_statuses.side_effect = GatusClientError(
        "Error communicating with Gatus API: status code 500"
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
