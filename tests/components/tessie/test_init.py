"""Test the Tessie init."""

from unittest.mock import AsyncMock, patch

from tesla_fleet_api.exceptions import (
    InvalidRequest,
    InvalidToken,
    ServiceUnavailable,
    TeslaFleetError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_load_unload(hass: HomeAssistant) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_runtime_vehicle_api_handle_is_optional(hass: HomeAssistant) -> None:
    """Test the runtime vehicle API handle remains optional during migration."""

    entry = await setup_platform(hass)
    assert all(vehicle.api is None for vehicle in entry.runtime_data.vehicles)


async def test_auth_failure(
    hass: HomeAssistant, mock_get_state_of_all_vehicles: AsyncMock
) -> None:
    """Test init with an authentication error."""

    mock_get_state_of_all_vehicles.side_effect = InvalidToken()
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unknown_failure(
    hass: HomeAssistant, mock_get_state_of_all_vehicles: AsyncMock
) -> None:
    """Test init with a non-retryable fleet API error."""

    mock_get_state_of_all_vehicles.side_effect = InvalidRequest()
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Failed to connect"


async def test_retryable_api_failure(
    hass: HomeAssistant, mock_get_state_of_all_vehicles: AsyncMock
) -> None:
    """Test init with a retryable fleet API error."""

    mock_get_state_of_all_vehicles.side_effect = ServiceUnavailable()
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_products_error(hass: HomeAssistant) -> None:
    """Test init with a fleet error on products."""

    with patch(
        "homeassistant.components.tessie.Tessie.products", side_effect=TeslaFleetError
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_scopes_error(hass: HomeAssistant) -> None:
    """Test init with a fleet error on scopes."""

    with patch(
        "homeassistant.components.tessie.Tessie.scopes", side_effect=TeslaFleetError
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_vehicle_api_handle_is_optional(hass: HomeAssistant) -> None:
    """Test runtime vehicle API handle defaults to None during scaffold stage."""

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    vehicles = entry.runtime_data.vehicles
    assert vehicles
    assert all(vehicle.api is None for vehicle in vehicles)
