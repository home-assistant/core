"""Test Autoskope coordinator."""

from unittest.mock import AsyncMock, patch

from autoskope_client.models import CannotConnect, InvalidAuth, Vehicle, VehiclePosition
import pytest

from homeassistant.components.autoskope.coordinator import (
    AutoskopeDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_init(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator initialization."""
    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    assert coordinator.name == "autoskope"
    assert coordinator.api == mock_autoskope_api
    assert coordinator.config_entry == mock_config_entry


async def test_coordinator_update_success(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
) -> None:
    """Test successful coordinator update."""
    # Setup mock responses
    mock_autoskope_api.get_vehicles.return_value = mock_vehicles_list

    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        # Call update using async_refresh to properly set coordinator.data
        await coordinator.async_refresh()

        # Verify API calls
        mock_autoskope_api.get_vehicles.assert_called_once()

        # Verify data structure
        assert coordinator.data is not None
        assert len(coordinator.data) == len(mock_vehicles_list)
        vehicle = mock_vehicles_list[0]
        assert vehicle.id in coordinator.data
        vehicle_obj = coordinator.data[vehicle.id]
        assert vehicle_obj.id == vehicle.id
        assert vehicle_obj.name == vehicle.name


async def test_coordinator_update_cannot_connect(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator update with connection error."""
    mock_autoskope_api.get_vehicles.side_effect = CannotConnect("Connection failed")

    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


async def test_coordinator_update_invalid_auth(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator update with authentication error."""
    mock_autoskope_api.get_vehicles.side_effect = InvalidAuth("Invalid credentials")
    # Make authenticate also fail
    mock_autoskope_api.authenticate.side_effect = InvalidAuth("Invalid credentials")

    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

        # Verify authenticate was called
        mock_autoskope_api.authenticate.assert_called_once()


async def test_coordinator_update_reauthentication_success(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
) -> None:
    """Test coordinator update with successful re-authentication."""
    # First call to get_vehicles fails with auth error
    # Second call after re-authentication succeeds
    mock_autoskope_api.get_vehicles.side_effect = [
        InvalidAuth("Session expired"),
        mock_vehicles_list,
    ]
    # Make authenticate succeed
    mock_autoskope_api.authenticate.return_value = None

    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        # Should succeed after re-authentication
        result = await coordinator._async_update_data()

        # Verify authenticate was called
        mock_autoskope_api.authenticate.assert_called_once()

        # Verify get_vehicles was called twice (initial failure, then retry)
        assert mock_autoskope_api.get_vehicles.call_count == 2

        # Verify data structure
        assert result is not None
        assert len(result) == len(mock_vehicles_list)
        vehicle = mock_vehicles_list[0]
        assert vehicle.id in result


async def test_coordinator_update_reauthentication_failure(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator update with failed re-authentication."""
    mock_autoskope_api.get_vehicles.side_effect = InvalidAuth("Session expired")
    # Make authenticate also fail
    mock_autoskope_api.authenticate.side_effect = InvalidAuth("Invalid credentials")

    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

        # Verify authenticate was called
        mock_autoskope_api.authenticate.assert_called_once()

        # Verify get_vehicles was only called once (before re-authentication attempt)
        mock_autoskope_api.get_vehicles.assert_called_once()


async def test_coordinator_update_unexpected_error(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator update with unexpected error."""
    mock_autoskope_api.get_vehicles.side_effect = Exception("Unexpected error")

    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


async def test_coordinator_update_empty_vehicles(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator update with empty vehicle list."""
    mock_autoskope_api.get_vehicles.return_value = []

    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        # Call the actual update method to set coordinator.data
        result = await coordinator._async_update_data()

        # Verify empty data (should be empty dict)
        assert result == {}


async def test_coordinator_multiple_vehicles(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator update with multiple vehicles."""
    # Create multiple test vehicles
    vehicle1 = Vehicle(
        id="vehicle1",
        name="Vehicle 1",
        position=VehiclePosition(
            latitude=50.1109221,
            longitude=8.6821267,
            speed=0,
            timestamp="2025-05-28T10:00:00Z",
            park_mode=False,
        ),
        external_voltage=12.5,
        battery_voltage=3.7,
        gps_quality=1.2,
        imei="123456789012345",
        model="Autoskope",
    )

    vehicle2 = Vehicle(
        id="vehicle2",
        name="Vehicle 2",
        position=VehiclePosition(
            latitude=50.2109221,
            longitude=8.7821267,
            speed=25,
            timestamp="2025-05-28T10:00:00Z",
            park_mode=False,
        ),
        external_voltage=12.8,
        battery_voltage=3.8,
        gps_quality=0.8,
        imei="987654321098765",
        model="Autoskope",
    )

    mock_autoskope_api.get_vehicles.return_value = [vehicle1, vehicle2]

    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        result = await coordinator._async_update_data()

        # Verify both vehicles are in data
        assert len(result) == 2
        assert "vehicle1" in result
        assert "vehicle2" in result
        assert result["vehicle1"].name == "Vehicle 1"
        assert result["vehicle2"].name == "Vehicle 2"


async def test_coordinator_logging_behavior(
    hass: HomeAssistant,
    mock_autoskope_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator logging behavior with repeated failures."""
    mock_autoskope_api.get_vehicles.side_effect = CannotConnect("Connection failed")

    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        # First failure should log
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        # Second failure should not log again (already logged)
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        # Reset to success should reset logging flag
        mock_autoskope_api.get_vehicles.side_effect = None
        mock_autoskope_api.get_vehicles.return_value = []

        await coordinator._async_update_data()

        # Next failure should log again
        mock_autoskope_api.get_vehicles.side_effect = CannotConnect("Connection failed")
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
