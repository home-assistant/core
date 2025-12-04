"""Test the Kiosker integration initialization."""

from unittest.mock import MagicMock, patch

from homeassistant.components.kiosker.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a successful setup entry and unload."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}

            await setup_integration(hass, mock_config_entry)
            assert mock_config_entry.state is ConfigEntryState.LOADED

            # Test unload
            assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
            await hass.async_block_till_done()
            assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an unsuccessful setup entry."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API that fails
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data",
            side_effect=Exception("Connection failed"),
        ):
            await setup_integration(hass, mock_config_entry)
            assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}

            await setup_integration(hass, mock_config_entry)

            # Check device was registered correctly
            device_entry = device_registry.async_get_device(
                identifiers={(DOMAIN, "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC")}
            )
            assert device_entry is not None
            assert device_entry.name == "Kiosker A98BE1CE"
            assert device_entry.manufacturer == "Top North"
            assert device_entry.model == "Kiosker"
            assert device_entry.sw_version == "25.1.1"
            assert device_entry.hw_version == "iPad Pro (18.0)"
            assert device_entry.serial_number == "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"


async def test_device_identifiers_and_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device identifiers and device info are set correctly."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data with specific device info
        mock_status = MagicMock()
        mock_status.device_id = "TEST_DEVICE_123"
        mock_status.model = "iPad Mini"
        mock_status.os_version = "17.5"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "24.1.0"

        mock_api.status.return_value = mock_status

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}

            await setup_integration(hass, mock_config_entry)

            # Check device was registered with correct info
            device_entry = device_registry.async_get_device(
                identifiers={(DOMAIN, "TEST_DEVICE_123")}
            )
            assert device_entry is not None
            assert device_entry.name == "Kiosker TEST_DEV"
            assert device_entry.manufacturer == "Top North"
            assert device_entry.model == "Kiosker"
            assert device_entry.sw_version == "24.1.0"
            assert device_entry.hw_version == "iPad Mini (17.5)"
            assert device_entry.serial_number == "TEST_DEVICE_123"
            assert device_entry.identifiers == {(DOMAIN, "TEST_DEVICE_123")}
