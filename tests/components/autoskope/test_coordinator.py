"""Tests for the coordinator module."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.autoskope.const import DOMAIN
from homeassistant.components.autoskope.coordinator import (
    AutoskopeDataUpdateCoordinator,
)
from homeassistant.components.autoskope.models import CannotConnect, InvalidAuth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import create_mock_vehicle

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api() -> AsyncMock:
    """Return a mock Autoskope API instance."""
    return AsyncMock()


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "test-user",
            "password": "test-pass",
            "host": "https://example.com",
        },
    )


async def test_coordinator_init(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator initialization."""
    coordinator = AutoskopeDataUpdateCoordinator(
        hass=hass, api=mock_api, entry=mock_config_entry
    )
    assert coordinator.api == mock_api
    assert coordinator.name == DOMAIN


async def test_coordinator_update_auth_failure(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator update raises ConfigEntryAuthFailed on InvalidAuth."""
    # Mock get_vehicles to raise InvalidAuth
    mock_api.get_vehicles.side_effect = InvalidAuth("Auth error")
    coordinator = AutoskopeDataUpdateCoordinator(
        hass=hass, api=mock_api, entry=mock_config_entry
    )

    # Expect ConfigEntryAuthFailed when _async_update_data is called
    with pytest.raises(
        ConfigEntryAuthFailed, match="Authentication failed: Auth error"
    ):
        await coordinator._async_update_data()


async def test_coordinator_update_success_list(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator update with successful list response."""
    # Create sample vehicles
    vehicle1 = create_mock_vehicle("123", "Vehicle 1")
    vehicle2 = create_mock_vehicle("456", "Vehicle 2")
    mock_vehicles_list = [vehicle1, vehicle2]
    mock_api.get_vehicles.return_value = mock_vehicles_list

    coordinator = AutoskopeDataUpdateCoordinator(
        hass=hass, api=mock_api, entry=mock_config_entry
    )
    result = await coordinator._async_update_data()

    # Assert the result is a dictionary keyed by vehicle ID
    assert isinstance(result, dict)
    assert len(result) == 2
    assert "123" in result
    assert "456" in result
    assert result["123"] == vehicle1
    assert result["456"] == vehicle2


async def test_coordinator_update_exception(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator update raises UpdateFailed on generic Exception."""
    # Mock API to raise generic Exception
    mock_api.get_vehicles.side_effect = Exception("API Error")
    coordinator = AutoskopeDataUpdateCoordinator(
        hass=hass, api=mock_api, entry=mock_config_entry
    )

    # Expect UpdateFailed when _async_update_data is called
    with pytest.raises(
        UpdateFailed, match="Unexpected error communicating with API: API Error"
    ):
        await coordinator._async_update_data()


async def test_coordinator_update_unknown_format(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator update raises UpdateFailed on unknown data format."""
    # Return unexpected data format
    mock_api.get_vehicles.return_value = "invalid data"
    coordinator = AutoskopeDataUpdateCoordinator(
        hass=hass, api=mock_api, entry=mock_config_entry
    )

    # Expect UpdateFailed when _async_update_data is called
    with pytest.raises(UpdateFailed, match="Unexpected data format: <class 'str'>"):
        await coordinator._async_update_data()


async def test_coordinator_update_generic_exception_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator refresh handling generic exceptions."""
    mock_config_entry.add_to_hass(hass)
    mock_api.get_vehicles.side_effect = Exception("Unexpected API error")
    coordinator = AutoskopeDataUpdateCoordinator(
        hass=hass, api=mock_api, entry=mock_config_entry
    )

    # Call async_refresh, don't expect it to raise
    await coordinator.async_refresh()

    # Assert update failed and check log message from coordinator base class
    assert coordinator.last_update_success is False
    assert (
        "Error fetching autoskope data: Unexpected error communicating with API: Unexpected API error"
        in caplog.text
    )


async def test_coordinator_update_connection_error_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator refresh handling connection errors."""
    mock_config_entry.add_to_hass(hass)
    mock_api.get_vehicles.side_effect = CannotConnect("Connection failed")
    coordinator = AutoskopeDataUpdateCoordinator(
        hass=hass, api=mock_api, entry=mock_config_entry
    )

    # Call async_refresh, don't expect it to raise
    await coordinator.async_refresh()

    # Assert update failed and check log message from coordinator base class
    assert coordinator.last_update_success is False
    assert (
        "Error fetching autoskope data: Error communicating with API: Connection failed"
        in caplog.text
    )


async def test_coordinator_update_auth_error_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator refresh handling authentication errors."""
    mock_config_entry.add_to_hass(hass)
    mock_api.get_vehicles.side_effect = InvalidAuth("Bad credentials")
    coordinator = AutoskopeDataUpdateCoordinator(
        hass=hass, api=mock_api, entry=mock_config_entry
    )

    # Call async_refresh, don't expect it to raise
    await coordinator.async_refresh()

    # Assert update failed and check log message from coordinator base class
    assert coordinator.last_update_success is False
    assert (
        "Authentication failed while fetching autoskope data: Authentication failed: Bad credentials"
        in caplog.text
    )


async def test_coordinator_update_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Test coordinator update failure due to InvalidAuth."""
    # Manually setup coordinator and add to hass.data
    mock_config_entry.add_to_hass(hass)
    # Pass mock_api to the constructor
    coordinator = AutoskopeDataUpdateCoordinator(hass, mock_api, mock_config_entry)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
        "api": mock_api,
        "coordinator": coordinator,
    }

    # Simulate InvalidAuth during fetch_devices for the actual test
    mock_api.get_vehicles.side_effect = InvalidAuth("Auth failed during update")

    # Expect ConfigEntryAuthFailed exception from _async_update_data
    with pytest.raises(ConfigEntryAuthFailed) as excinfo:
        await coordinator._async_update_data()

    assert "Authentication failed" in str(excinfo.value)
    mock_api.get_vehicles.assert_awaited_once()


async def test_coordinator_update_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Test coordinator update failure due to CannotConnect."""
    # Manually setup coordinator and add to hass.data
    mock_config_entry.add_to_hass(hass)
    # Pass mock_api to the constructor
    coordinator = AutoskopeDataUpdateCoordinator(hass, mock_api, mock_config_entry)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
        "api": mock_api,
        "coordinator": coordinator,
    }

    # Simulate CannotConnect during fetch_devices for the actual test
    mock_api.get_vehicles.side_effect = CannotConnect("Connection failed during update")

    # Expect UpdateFailed exception from _async_update_data
    with pytest.raises(UpdateFailed) as excinfo:
        await coordinator._async_update_data()

    assert "Error communicating with API" in str(excinfo.value)
    mock_api.get_vehicles.assert_awaited_once()


async def test_coordinator_invalid_auth(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handling InvalidAuth."""
    # Pass mock_config_entry to the constructor
    coordinator = AutoskopeDataUpdateCoordinator(hass, mock_api, mock_config_entry)

    # Mock get_vehicles to raise InvalidAuth
    mock_api.get_vehicles.side_effect = InvalidAuth("API auth failed")

    # Expect ConfigEntryAuthFailed when update is called
    with pytest.raises(ConfigEntryAuthFailed):
        # Need to call _async_update_data directly to see the exception
        # async_refresh catches it and logs it
        await coordinator._async_update_data()

    mock_api.get_vehicles.assert_called_once()
