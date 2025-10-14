"""Tests for the Watts Vision coordinator."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from visionpluspython.client import WattsVisionClient
from visionpluspython.models import Device

from homeassistant.components.watts.coordinator import (
    WattsVisionDeviceCoordinator,
    WattsVisionHubCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

DOMAIN = "watts"
UPDATE_INTERVAL = 30


@pytest.fixture
def mock_hass():
    """Mock HomeAssistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_config_entry():
    """Mock ConfigEntry instance."""
    return MagicMock(spec=ConfigEntry)


@pytest.fixture
def mock_client():
    """Mock WattsVisionClient instance."""
    client = MagicMock(spec=WattsVisionClient)
    client.discover_devices = AsyncMock()
    client.get_device = AsyncMock()
    client.get_devices_report = AsyncMock()
    return client


@pytest.fixture
def mock_device():
    """Mock Watts Vision device."""
    device = MagicMock(spec=Device)
    device.device_id = "device_123"
    device.device_name = "Test Device"
    return device


@pytest.fixture
def hub_coordinator(mock_hass, mock_client, mock_config_entry):
    """Create a WattsVisionHubCoordinator instance."""
    return WattsVisionHubCoordinator(mock_hass, mock_client, mock_config_entry)


@pytest.fixture
def device_coordinator(mock_hass, mock_client, mock_config_entry):
    """Create a WattsVisionDeviceCoordinator instance."""
    return WattsVisionDeviceCoordinator(
        mock_hass, mock_client, mock_config_entry, "device_123"
    )


class TestWattsVisionHubCoordinator:
    """Test the hub coordinator."""

    async def test_hub_coordinator_initialization(
        self, hub_coordinator, mock_hass, mock_client
    ) -> None:
        """Test hub coordinator initialization."""
        assert hub_coordinator.hass == mock_hass
        assert hub_coordinator.client == mock_client
        assert hub_coordinator.name == DOMAIN
        assert hub_coordinator.update_interval.total_seconds() == UPDATE_INTERVAL
        assert hub_coordinator._is_initialized is False
        assert hub_coordinator._devices == {}

    async def test_async_config_entry_first_refresh_success(
        self, hub_coordinator, mock_client, mock_device
    ) -> None:
        """Test successful initial device discovery."""
        mock_client.discover_devices.return_value = [mock_device]

        await hub_coordinator.async_config_entry_first_refresh()

        mock_client.discover_devices.assert_called_once()
        assert hub_coordinator._is_initialized is True
        assert hub_coordinator._devices == {mock_device.device_id: mock_device}

    async def test_async_config_entry_first_refresh_failure(
        self, hub_coordinator, mock_client
    ) -> None:
        """Test failed initial device discovery."""
        mock_client.discover_devices.side_effect = ConnectionError("API error")

        with pytest.raises(UpdateFailed):
            await hub_coordinator.async_config_entry_first_refresh()

        assert hub_coordinator._is_initialized is False
        assert hub_coordinator._devices == {}

    async def test_async_update_data_not_initialized(
        self, hub_coordinator, mock_client, mock_device
    ) -> None:
        """Test _async_update_data when coordinator is not initialized."""
        mock_client.discover_devices.return_value = [mock_device]

        result = await hub_coordinator._async_update_data()

        mock_client.discover_devices.assert_called_once()
        assert hub_coordinator._is_initialized is True
        assert result == {mock_device.device_id: mock_device}

    async def test_async_update_data_no_devices(
        self, hub_coordinator, mock_client
    ) -> None:
        """Test _async_update_data when no devices are known."""
        hub_coordinator._is_initialized = True
        hub_coordinator._devices = {}

        result = await hub_coordinator._async_update_data()

        mock_client.get_devices_report.assert_not_called()
        assert result == {}

    async def test_async_update_data_success(
        self, hub_coordinator, mock_client, mock_device
    ) -> None:
        """Test successful device report update."""
        hub_coordinator._is_initialized = True
        hub_coordinator._devices = {mock_device.device_id: mock_device}
        updated_device = MagicMock(spec=Device)
        updated_device.device_id = mock_device.device_id
        mock_client.get_devices_report.return_value = {
            mock_device.device_id: updated_device
        }

        result = await hub_coordinator._async_update_data()

        mock_client.get_devices_report.assert_called_once_with([mock_device.device_id])
        assert hub_coordinator._devices[mock_device.device_id] == updated_device
        assert result == {mock_device.device_id: updated_device}

    async def test_device_ids_property(self, hub_coordinator, mock_device) -> None:
        """Test device_ids property."""
        hub_coordinator._devices = {mock_device.device_id: mock_device}

        assert hub_coordinator.device_ids == [mock_device.device_id]


class TestWattsVisionDeviceCoordinator:
    """Test the device coordinator."""

    async def test_device_coordinator_initialization(
        self, device_coordinator, mock_hass, mock_client
    ) -> None:
        """Test device coordinator initialization."""
        assert device_coordinator.hass == mock_hass
        assert device_coordinator.client == mock_client
        assert device_coordinator.name == f"{DOMAIN}_device_123"
        assert device_coordinator.update_interval is None  # Manual refresh only
        assert device_coordinator.device_id == "device_123"
        assert device_coordinator._fast_polling_until is None

    async def test_async_set_updated_data(
        self, device_coordinator, mock_device
    ) -> None:
        """Test setting initial data from hub coordinator."""
        device_coordinator.async_set_updated_data(mock_device)

        assert device_coordinator.data == mock_device

    async def test_async_update_data_success(
        self, device_coordinator, mock_client, mock_device
    ) -> None:
        """Test successful device refresh."""
        mock_client.get_device.return_value = mock_device

        result = await device_coordinator._async_update_data()

        mock_client.get_device.assert_called_once_with("device_123", refresh=True)
        assert result == mock_device

    async def test_async_update_data_device_not_found(
        self, device_coordinator, mock_client
    ) -> None:
        """Test device refresh when device is not found."""
        mock_client.get_device.return_value = None

        result = await device_coordinator._async_update_data()

        mock_client.get_device.assert_called_once_with("device_123", refresh=True)
        assert result is None

    async def test_async_update_data_failure(
        self, device_coordinator, mock_client
    ) -> None:
        """Test device refresh when API call fails."""
        mock_client.get_device.side_effect = ConnectionError("Refresh error")

        with pytest.raises(UpdateFailed):
            await device_coordinator._async_update_data()

        mock_client.get_device.assert_called_once_with("device_123", refresh=True)

    async def test_trigger_fast_polling(self, device_coordinator) -> None:
        """Test triggering fast polling on device coordinator."""
        with patch(
            "homeassistant.components.watts.coordinator.datetime"
        ) as mock_datetime:
            mock_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now

            device_coordinator.trigger_fast_polling(60)

            assert device_coordinator._fast_polling_until == mock_now + timedelta(
                seconds=60
            )
            assert device_coordinator.update_interval == timedelta(seconds=5)

    async def test_fast_polling_expires(
        self, device_coordinator, mock_client, mock_device
    ) -> None:
        """Test that fast polling expires and returns to manual refresh."""
        mock_client.get_device.return_value = mock_device

        # Set up fast polling that has expired
        past_time = datetime.now() - timedelta(seconds=1)
        device_coordinator._fast_polling_until = past_time
        device_coordinator.update_interval = timedelta(seconds=5)

        result = await device_coordinator._async_update_data()

        # Should have reset fast polling
        assert device_coordinator._fast_polling_until is None
        assert device_coordinator.update_interval is None
        assert result == mock_device

    async def test_fast_polling_active(
        self, device_coordinator, mock_client, mock_device
    ) -> None:
        """Test that fast polling remains active when not expired."""
        mock_client.get_device.return_value = mock_device

        # Set up fast polling that hasn't expired
        future_time = datetime.now() + timedelta(seconds=30)
        device_coordinator._fast_polling_until = future_time
        device_coordinator.update_interval = timedelta(seconds=5)

        result = await device_coordinator._async_update_data()

        # Should keep fast polling active
        assert device_coordinator._fast_polling_until == future_time
        assert device_coordinator.update_interval == timedelta(seconds=5)
        assert result == mock_device
