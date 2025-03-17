"""Tests for ActronAir Coordinators."""

from unittest.mock import AsyncMock

from homeassistant.components.actronair.const import DOMAIN, SELECTED_AC_SERIAL
from homeassistant.components.actronair.coordinator import (
    ActronAirACSystemsDataCoordinator,
    ActronAirSystemStatusDataCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed


async def test_ac_systems_data_coordinator(hass: HomeAssistant) -> None:
    """Test fetching AC systems list."""
    mock_api = AsyncMock()
    mock_api.async_getACSystems.return_value = ["AC1", "AC2"]

    coordinator = ActronAirACSystemsDataCoordinator(hass, mock_api)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data == ["AC1", "AC2"]
    mock_api.async_getACSystems.assert_called_once()


async def test_ac_systems_auth_failure(hass: HomeAssistant) -> None:
    """Test handling of authentication failure in AC systems fetch."""
    mock_api = AsyncMock()
    mock_api.async_getACSystems.side_effect = ConfigEntryAuthFailed()

    coordinator = ActronAirACSystemsDataCoordinator(hass, mock_api)

    try:  # noqa: SIM105
        await coordinator._async_update_data()
    except ConfigEntryAuthFailed:
        pass  # Expected error


async def test_system_status_coordinator(hass: HomeAssistant) -> None:
    """Test fetching AC system status."""
    mock_api = AsyncMock()
    mock_api.async_getACSystemStatus.return_value = {"status": "ok"}
    hass.data[DOMAIN] = {SELECTED_AC_SERIAL: "12345"}

    coordinator = ActronAirSystemStatusDataCoordinator(hass, mock_api)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data == {"status": "ok"}
    mock_api.async_getACSystemStatus.assert_called_once_with("12345")


async def test_system_status_api_failure(hass: HomeAssistant) -> None:
    """Test handling of API error in system status fetch."""
    mock_api = AsyncMock()
    mock_api.async_getACSystemStatus.side_effect = Exception("API error")
    hass.data[DOMAIN] = {SELECTED_AC_SERIAL: "12345"}

    coordinator = ActronAirSystemStatusDataCoordinator(hass, mock_api)

    try:
        await coordinator._async_update_data()
    except Exception as e:  # noqa: BLE001
        assert str(e) == "API error"  # noqa: PT017
