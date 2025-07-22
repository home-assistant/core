"""Coordinator Ubiquiti airOS tests."""

from asyncio import TimeoutError
from unittest.mock import AsyncMock

from airos.exceptions import (
    ConnectionAuthenticationError,
    ConnectionSetupError,
    DataMissingError,
    DeviceConnectionError,
)
import pytest

from homeassistant.components.airos.coordinator import (
    AirOSData,
    AirOSDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import ConfigEntryError, UpdateFailed


@pytest.fixture
def mock_hass():
    """Mock HomeAssistant instance."""
    return AsyncMock(spec=HomeAssistant)


async def test_async_update_data_success(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_airos_client: AsyncMock,
    ap_fixture: AirOSData,
) -> None:
    """Test async_update_data succeeds and returns data."""
    mock_airos_client.return_value.login.return_value = True
    mock_airos_client.return_value.status.return_value = ap_fixture

    coordinator = AirOSDataUpdateCoordinator(
        mock_hass, mock_config_entry, mock_airos_client.return_value
    )
    data = await coordinator._async_update_data()

    mock_airos_client.return_value.login.assert_called_once()
    mock_airos_client.return_value.status.assert_called_once()
    assert isinstance(data, AirOSData)
    assert data == ap_fixture


async def test_async_update_data_connection_authentication_error(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_airos_client: AsyncMock,
) -> None:
    """Test async_update_data handles ConnectionAuthenticationError."""
    mock_airos_client.return_value.login.side_effect = ConnectionAuthenticationError(
        "Auth failed"
    )
    coordinator = AirOSDataUpdateCoordinator(
        mock_hass, mock_config_entry, mock_airos_client.return_value
    )

    with pytest.raises(ConfigEntryError) as excinfo:
        await coordinator._async_update_data()
    assert excinfo.value.translation_key == "invalid_auth"
    mock_airos_client.return_value.login.assert_called_once()
    mock_airos_client.return_value.status.assert_not_called()


@pytest.mark.parametrize(
    "exception_type",
    [ConnectionSetupError, DeviceConnectionError, TimeoutError],
)
async def test_async_update_data_cannot_connect_errors(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_airos_client: AsyncMock,
    exception_type: Exception,
) -> None:
    """Test async_update_data handles various connection errors."""
    mock_airos_client.return_value.login.side_effect = exception_type(
        "Connection failed"
    )
    coordinator = AirOSDataUpdateCoordinator(
        mock_hass, mock_config_entry, mock_airos_client.return_value
    )

    with pytest.raises(UpdateFailed) as excinfo:
        await coordinator._async_update_data()
    assert excinfo.value.translation_key == "cannot_connect"
    mock_airos_client.return_value.login.assert_called_once()
    mock_airos_client.return_value.status.assert_not_called()


async def test_async_update_data_data_missing_error(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_airos_client: AsyncMock,
) -> None:
    """Test async_update_data handles DataMissingError."""
    mock_airos_client.return_value.login.return_value = True
    mock_airos_client.return_value.status.side_effect = DataMissingError(
        "Missing data from device"
    )
    coordinator = AirOSDataUpdateCoordinator(
        mock_hass, mock_config_entry, mock_airos_client.return_value
    )

    with pytest.raises(UpdateFailed) as excinfo:
        await coordinator._async_update_data()
    assert excinfo.value.translation_key == "error_data_missing"
    mock_airos_client.return_value.login.assert_called_once()
    mock_airos_client.return_value.status.assert_called_once()
