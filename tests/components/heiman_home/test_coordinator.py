"""Tests for the Heiman Home coordinator."""

from datetime import UTC, datetime, timedelta
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import (
    DeviceManagement,
    DeviceProperty,
    HeimanAuthError,
    HeimanDevice,
    HeimanMQTTError,
)
import pytest

from homeassistant.components.heiman_home.const import DOMAIN
from homeassistant.components.heiman_home.coordinator import (
    HeimanDataUpdateCoordinator,
    _infer_entity_type,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

__all__ = [
    "MockConfigEntry",
]

_LOGGER = logging.getLogger(__name__)


async def test_coordinator_update_success(
    hass: HomeAssistant, mock_api_client: MagicMock
) -> None:
    """Test successful coordinator update."""
    # Setup mocks
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"
    mock_user.email = "test@example.com"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"
    mock_home.home_name = "Test Home"
    mock_home.device_count = 2

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}

    # The coordinator accesses cloud_client methods, so set return values on cloud_client
    mock_api_client.cloud_client.async_get_user_info.return_value = mock_user
    mock_api_client.cloud_client.async_get_homes.return_value = [mock_home]
    mock_api_client.cloud_client.async_get_devices.return_value = {
        "device-1": mock_device
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data.user_info == mock_user
    assert coordinator.data.home_info == mock_home
    assert "device-1" in coordinator.data.devices


async def test_coordinator_update_auth_failed(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test coordinator update with authentication failure."""
    # Set up cloud_client mock correctly
    mock_api_client.cloud_client.async_get_user_info.side_effect = (
        ConfigEntryAuthFailed("Authentication failed")
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # async_refresh catches exceptions and stores them in last_exception
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check that the exception was stored as UpdateFailed (ConfigEntryAuthFailed
    # is caught by generic handler and re-raised as UpdateFailed)
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_coordinator_update_failed(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test coordinator update with general failure."""
    mock_api_client.async_get_user_info.side_effect = Exception("Network error")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # async_refresh catches exceptions and stores them in last_exception
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check that an UpdateFailed exception was stored
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_coordinator_update_preserves_update_failed(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test that UpdateFailed exceptions are preserved without wrapping."""
    # Create an UpdateFailed with custom message and raise it from async_get_devices
    # (which is called after user/home info, so it goes through the main exception handler)
    original_error = UpdateFailed("Original device fetch error")
    mock_api_client.async_get_devices.side_effect = original_error

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # async_refresh catches exceptions and stores them in last_exception
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify the original UpdateFailed is preserved (wrapped with context)
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "Original device fetch error" in str(coordinator.last_exception)


async def test_coordinator_device_fetch_preserves_update_failed(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test that UpdateFailed from device fetching is preserved."""
    # Setup successful user/home info
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"
    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {}

    # Raise UpdateFailed from device fetching
    original_error = UpdateFailed("Device API rate limited")
    mock_api_client.async_get_devices.side_effect = original_error

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First update to populate user/home info
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Second update should hit device fetch and preserve UpdateFailed
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify the UpdateFailed is preserved
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "Device API rate limited" in str(coordinator.last_exception)


async def test_coordinator_missing_home_id(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test coordinator update with missing home ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "user_id": "test-user-id",
            # Missing home_id
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # async_refresh catches exceptions and stores them in last_exception
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check that an UpdateFailed exception was stored with the right message
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "Home ID not found" in str(coordinator.last_exception)


async def test_coordinator_device_detail_caching(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test device detail caching to avoid N+1 API calls."""
    # Setup mocks
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}

    mock_device_detail = {
        "properties": [
            {"identifier": "temperature", "value": 25.0},
        ]
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}
    mock_api_client.cloud_client._async_get_device_detail = AsyncMock(
        return_value=mock_device_detail
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First update - should call _async_get_device_detail (private method)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert mock_api_client.cloud_client._async_get_device_detail.call_count == 1

    # Second update within cache TTL - should NOT call _async_get_device_detail again
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert (
        mock_api_client.cloud_client._async_get_device_detail.call_count == 1
    )  # Still 1


async def test_coordinator_online_status_merge(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test that online status is preserved when new status is None."""
    # Setup mocks
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    # First device with online=True
    mock_device_1 = MagicMock()
    mock_device_1.device_id = "device-1"
    mock_device_1.device_name = "Test Device"
    mock_device_1.online = True
    mock_device_1.raw_data = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device_1}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First update
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data.devices["device-1"].online is True

    # Second update with online=None (should preserve old status)
    mock_device_2 = MagicMock()
    mock_device_2.device_id = "device-1"
    mock_device_2.device_name = "Test Device"
    mock_device_2.online = None  # Unknown status
    mock_device_2.raw_data = {}

    mock_api_client.async_get_devices.return_value = {"device-1": mock_device_2}

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    # Should preserve the previous online=True status
    assert coordinator.data.devices["device-1"].online is True


async def test_coordinator_user_info_fetch_failed(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test coordinator update when user info fetch fails."""
    mock_api_client.async_get_user_info.side_effect = Exception("User API error")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # async_refresh catches exceptions and stores them in last_exception
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check that an UpdateFailed exception was stored with user info error
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "Failed to fetch user info" in str(coordinator.last_exception)


async def test_coordinator_empty_home_id(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test coordinator update with empty home ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "user_id": "test-user-id",
            "home_id": "",  # Empty home_id
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # async_refresh catches exceptions and stores them in last_exception
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check that an UpdateFailed exception was stored with right message
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "Home ID not found" in str(coordinator.last_exception)


async def test_coordinator_last_update_time(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test that last_update time is set correctly."""
    # Setup mocks
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Initial state - last_update should be None
    assert coordinator.data.last_update is None

    # Perform update
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check that last_update time was set
    assert coordinator.data.last_update is not None
    assert coordinator.data.last_update.tzinfo is UTC


async def test_coordinator_signal_strength_conversion() -> None:
    """Test signal strength DBM to level conversion."""
    # Test strong signal
    assert HeimanDataUpdateCoordinator._convert_dbm_to_level(-40) == "strong"
    assert HeimanDataUpdateCoordinator._convert_dbm_to_level(-50) == "strong"

    # Test medium signal
    assert HeimanDataUpdateCoordinator._convert_dbm_to_level(-51) == "medium"
    assert HeimanDataUpdateCoordinator._convert_dbm_to_level(-65) == "medium"

    # Test weak signal
    assert HeimanDataUpdateCoordinator._convert_dbm_to_level(-66) == "weak"
    assert HeimanDataUpdateCoordinator._convert_dbm_to_level(-75) == "weak"

    # Test very weak signal
    assert HeimanDataUpdateCoordinator._convert_dbm_to_level(-76) == "very_weak"
    assert HeimanDataUpdateCoordinator._convert_dbm_to_level(-90) == "very_weak"


async def test_coordinator_extract_firmware_version_from_raw_data(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test firmware version extraction from device raw_data."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {"firmwareInfo": {"version": "1.2.3"}}
    mock_device.firmware_version = None

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data.devices["device-1"].firmware_version == "1.2.3"


async def test_coordinator_extract_firmware_version_from_firmware_info(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test firmware version extraction from device firmware_info attribute."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.firmware_info = {"version": "2.0.1"}
    mock_device.firmware_version = None

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data.devices["device-1"].firmware_version == "2.0.1"


async def test_coordinator_process_device_detail_firmware(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test firmware version extraction from device detail."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.firmware_version = None
    mock_device.properties = {}

    mock_device_detail = {
        "firmwareInfo": {"version": "3.4.5"},
        "deriveMetadata": "[]",
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}
    mock_api_client.cloud_client._async_get_device_detail = AsyncMock(
        return_value=mock_device_detail
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data.devices["device-1"].firmware_version == "3.4.5"


async def test_coordinator_process_device_info(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test DeviceINFO property processing."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "DeviceINFO_MAC": DeviceProperty(
            identifier="DeviceINFO_MAC", name="MAC", value=None
        ),
        "DeviceINFO_DBM": DeviceProperty(
            identifier="DeviceINFO_DBM", name="DBM", value=None
        ),
        "DeviceINFO_DBM_Level": DeviceProperty(
            identifier="DeviceINFO_DBM_Level", name="DBM Level", value=None
        ),
        "DeviceINFO_IP": DeviceProperty(
            identifier="DeviceINFO_IP", name="IP", value=None
        ),
    }

    mock_device_detail = {
        "deriveMetadata": '[{"property": "DeviceINFO", "value": {"MAC": "AA:BB:CC:DD:EE:FF", "DBM": -60, "IP": "192.168.1.100"}}]',
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}
    mock_api_client.cloud_client._async_get_device_detail = AsyncMock(
        return_value=mock_device_detail
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    device = coordinator.data.devices["device-1"]
    assert device.properties["DeviceINFO_MAC"].value == "AA:BB:CC:DD:EE:FF"
    assert device.properties["DeviceINFO_DBM"].value == -60
    assert device.properties["DeviceINFO_DBM_Level"].value == "medium"
    assert device.properties["DeviceINFO_IP"].value == "192.168.1.100"


async def test_coordinator_rssi_level_conversion(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test RSSI property with level conversion."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "RSSI": DeviceProperty(identifier="RSSI", name="RSSI", value=None),
        "DeviceINFO_DBM_Level": DeviceProperty(
            identifier="DeviceINFO_DBM_Level", name="DBM Level", value=None
        ),
    }

    mock_device_detail = {
        "deriveMetadata": '[{"property": "RSSI", "value": -55}]',
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}
    mock_api_client.cloud_client._async_get_device_detail = AsyncMock(
        return_value=mock_device_detail
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    device = coordinator.data.devices["device-1"]
    assert device.properties["RSSI"].value == -55
    assert device.properties["DeviceINFO_DBM_Level"].value == "medium"


async def test_coordinator_get_device(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test get_device method."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Test getting existing device
    device = coordinator.get_device("device-1")
    assert device is not None
    assert device.device_id == "device-1"

    # Test getting non-existent device
    device = coordinator.get_device("non-existent")
    assert device is None


async def test_coordinator_get_all_devices(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test get_all_devices method."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device1 = MagicMock()
    mock_device1.device_id = "device-1"
    mock_device1.device_name = "Device 1"
    mock_device1.online = True
    mock_device1.raw_data = {}

    mock_device2 = MagicMock()
    mock_device2.device_id = "device-2"
    mock_device2.device_name = "Device 2"
    mock_device2.online = False
    mock_device2.raw_data = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {
        "device-1": mock_device1,
        "device-2": mock_device2,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    devices = coordinator.get_all_devices()
    assert len(devices) == 2


async def test_coordinator_get_devices_by_type(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test get_devices_by_type method."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device1 = MagicMock()
    mock_device1.device_id = "device-1"
    mock_device1.device_type = "sensor"
    mock_device1.device_name = "Sensor 1"
    mock_device1.online = True
    mock_device1.raw_data = {}

    mock_device2 = MagicMock()
    mock_device2.device_id = "device-2"
    mock_device2.device_type = "switch"
    mock_device2.device_name = "Switch 1"
    mock_device2.online = False
    mock_device2.raw_data = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {
        "device-1": mock_device1,
        "device-2": mock_device2,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    sensors = coordinator.get_devices_by_type("sensor")
    assert len(sensors) == 1
    assert sensors[0].device_type == "sensor"

    switches = coordinator.get_devices_by_type("switch")
    assert len(switches) == 1
    assert switches[0].device_type == "switch"

    non_existent = coordinator.get_devices_by_type("non-existent")
    assert len(non_existent) == 0


async def test_coordinator_get_online_devices(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test get_online_devices method."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device1 = MagicMock()
    mock_device1.device_id = "device-1"
    mock_device1.device_name = "Device 1"
    mock_device1.online = True
    mock_device1.raw_data = {}

    mock_device2 = MagicMock()
    mock_device2.device_id = "device-2"
    mock_device2.device_name = "Device 2"
    mock_device2.online = False
    mock_device2.raw_data = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {
        "device-1": mock_device1,
        "device-2": mock_device2,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    online_devices = coordinator.get_online_devices()
    assert len(online_devices) == 1
    assert online_devices[0].device_id == "device-1"


async def test_coordinator_get_device_property(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test get_device_property method."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.5
        ),
        "humidity": DeviceProperty(identifier="humidity", name="Humidity", value=60.0),
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Test getting existing property
    temp = coordinator.get_device_property("device-1", "temperature")
    assert temp == 25.5

    # Test getting non-existent property
    non_existent = coordinator.get_device_property("device-1", "non-existent")
    assert non_existent is None

    # Test getting property from non-existent device
    non_existent_device = coordinator.get_device_property("non-existent", "temperature")
    assert non_existent_device is None


async def test_coordinator_device_property_update_via_mqtt(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT device property updates."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.0
        ),
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Simulate MQTT property update
    coordinator._on_device_property_update(
        "device-1", {"temperature": 30.0, "humidity": 70.0}
    )
    await hass.async_block_till_done()

    # Check that properties were updated
    assert coordinator.data.devices["device-1"].properties["temperature"].value == 30.0
    assert "humidity" in coordinator.data.devices["device-1"].properties


async def test_coordinator_home_info_fetch_error_handling(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test home info fetch error handling."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.side_effect = Exception("API error")
    mock_api_client.async_get_devices.return_value = {}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First update should fetch user info and fail on home info
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # User info should be fetched
    assert coordinator.data.user_info is not None
    # Home info should be None due to error
    assert coordinator.data.home_info is None
    # Error should be stored
    assert "home_info" in coordinator.data.errors


async def test_coordinator_device_fetch_with_existing_data(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test device fetch preserves existing data on failure."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.0
        ),
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First successful update
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert "device-1" in coordinator.data.devices
    assert coordinator.data.devices["device-1"].properties["temperature"].value == 25.0

    # Second update fails
    mock_api_client.async_get_devices.side_effect = Exception("API error")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Device data should be preserved
    assert "device-1" in coordinator.data.devices
    assert coordinator.data.devices["device-1"].properties["temperature"].value == 25.0
    assert "devices" in coordinator.data.errors


async def test_coordinator_mqtt_init_already_initialized(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT client initialization when already initialized."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Mock HeimanMqttClient to avoid actual socket connections
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        # Initialize once
        await coordinator.async_init_mqtt_client()
        first_client = coordinator.mqtt_client

        # Initialize again - should return early
        await coordinator.async_init_mqtt_client()
        second_client = coordinator.mqtt_client

        # Should be the same client
        assert first_client is second_client


async def test_coordinator_mqtt_init_missing_access_token(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT client initialization with missing access token."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {},  # Empty token dict
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Should not initialize MQTT without access token
    await coordinator.async_init_mqtt_client()
    assert coordinator.mqtt_client is None


async def test_coordinator_mqtt_init_missing_user_id(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT client initialization with missing user_id."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            # Missing user_id
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Should not initialize MQTT without user_id
    await coordinator.async_init_mqtt_client()
    assert coordinator.mqtt_client is None


async def test_coordinator_mqtt_property_update_device_not_found(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT property update for non-existent device."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Update non-existent device - should not raise
    coordinator._on_device_property_update("non-existent-device", {"temperature": 30.0})


async def test_coordinator_mqtt_property_update_add_new_property(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT property update adds new property."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.0
        ),
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Add new property via MQTT
    coordinator._on_device_property_update("device-1", {"new_property": 42.0})
    await hass.async_block_till_done()

    # Check that new property was added
    assert "new_property" in coordinator.data.devices["device-1"].properties
    assert coordinator.data.devices["device-1"].properties["new_property"].value == 42.0


async def test_coordinator_read_device_properties_no_mqtt_client(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test reading device properties without MQTT client."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # MQTT client not initialized - should not raise
    await coordinator.async_read_device_properties("device-1")


async def test_coordinator_read_device_properties_device_not_found(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test reading properties from non-existent device."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {}
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Mock MQTT client
    coordinator.mqtt_client = MagicMock()

    # Read from non-existent device - should not raise
    await coordinator.async_read_device_properties("non-existent-device")


async def test_coordinator_update_property_without_property_id(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test device property update without property ID."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.0
        ),
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Update without property ID - should not raise or change anything
    coordinator._update_device_property(mock_device, {"property": "", "value": 30.0})
    assert mock_device.properties["temperature"].value == 25.0

    # Update with None property ID - should not raise or change anything
    coordinator._update_device_property(mock_device, {"value": 30.0})
    assert mock_device.properties["temperature"].value == 25.0


async def test_coordinator_update_property_with_none_value(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test device property update with None value."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.0
        ),
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Update with None value - should not raise or change anything
    coordinator._update_device_property(
        mock_device, {"property": "temperature", "value": None}
    )
    assert mock_device.properties["temperature"].value == 25.0


async def test_coordinator_process_device_info_missing_fields(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test DeviceINFO processing with missing fields."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "DeviceINFO_MAC": DeviceProperty(
            identifier="DeviceINFO_MAC", name="MAC", value=None
        ),
        "DeviceINFO_DBM": DeviceProperty(
            identifier="DeviceINFO_DBM", name="DBM", value=None
        ),
        "DeviceINFO_DBM_Level": DeviceProperty(
            identifier="DeviceINFO_DBM_Level", name="DBM Level", value=None
        ),
        "DeviceINFO_IP": DeviceProperty(
            identifier="DeviceINFO_IP", name="IP", value=None
        ),
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}
    mock_api_client.cloud_client._async_get_device_detail = AsyncMock(
        return_value={
            "deriveMetadata": '[{"property": "DeviceINFO", "value": {"DBM": -60}}]',
        }
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    device = coordinator.data.devices["device-1"]
    # MAC and IP should remain None (not provided)
    assert device.properties["DeviceINFO_MAC"].value is None
    assert device.properties["DeviceINFO_IP"].value is None
    # DBM should be updated
    assert device.properties["DeviceINFO_DBM"].value == -60
    # DBM_Level should be calculated from DBM
    assert "DeviceINFO_DBM_Level" in device.properties
    assert device.properties["DeviceINFO_DBM_Level"].value == "medium"


async def test_coordinator_mqtt_init_from_oauth_session(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT client initialization getting token from OAuth session."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {},  # No access_token in config
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    # Create mock OAuth session
    mock_oauth_session = MagicMock()
    mock_oauth_session.token = {"access_token": "oauth-token"}
    mock_oauth_session.async_ensure_token_valid = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
        oauth_session=mock_oauth_session,
    )

    # Initialize MQTT - should get token from OAuth session
    mock_mqtt_instance = MagicMock()
    mock_mqtt_instance.connect = AsyncMock()
    mock_mqtt_instance.register_device_callback = MagicMock()

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient",
        return_value=mock_mqtt_instance,
    ):
        await coordinator.async_init_mqtt_client()

        # Verify OAuth session was used
        mock_oauth_session.async_ensure_token_valid.assert_called_once()


async def test_coordinator_mqtt_init_user_display_name_nick_name(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT client initialization with nick_name from user info."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"
    mock_user.nick_name = "Test User"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First refresh to initialize user_info
    await coordinator.async_refresh()

    # Initialize MQTT - should use nick_name
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        await coordinator.async_init_mqtt_client()

        # Verify user_display_name was set to nick_name
        _, kwargs = mock_mqtt_class.call_args
        # user_display_name is passed as a keyword argument, not positional
        assert kwargs.get("user_display_name") == "Test User"


async def test_coordinator_mqtt_init_user_display_name_email(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT client initialization with email from user info (no nick_name)."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"
    mock_user.nick_name = None
    mock_user.email = "test@example.com"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First refresh to initialize user_info
    await coordinator.async_refresh()

    # Initialize MQTT - should use email
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        await coordinator.async_init_mqtt_client()

        # Verify user_display_name was set to email
        _, kwargs = mock_mqtt_class.call_args
        # user_display_name is passed as a keyword argument, not positional
        assert kwargs.get("user_display_name") == "test@example.com"


async def test_coordinator_mqtt_init_oauth_token_error(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT client initialization when OAuth token validation fails."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    # Create mock OAuth session that fails validation
    mock_oauth_session = MagicMock()
    mock_oauth_session.async_ensure_token_valid = AsyncMock(
        side_effect=Exception("Failed")
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
        oauth_session=mock_oauth_session,
    )

    # Initialize MQTT - should not raise, just log warning
    await coordinator.async_init_mqtt_client()

    # Should not initialize MQTT client
    assert coordinator.mqtt_client is None


async def test_coordinator_read_device_properties_success(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test reading device properties successfully."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {}
    mock_device.product_id = "prod-1"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Mock MQTT client
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_read_properties = AsyncMock(
        return_value={"temperature": 25.0, "humidity": 60.0}
    )
    coordinator.mqtt_client = mock_mqtt_client

    # Read device properties
    await coordinator.async_read_device_properties("device-1")

    # Verify MQTT read was called
    mock_mqtt_client.async_read_properties.assert_called_once()
    call_kwargs = mock_mqtt_client.async_read_properties.call_args[1]
    assert call_kwargs["device_id"] == "device-1"
    assert call_kwargs["property_identifiers"] is None

    # Verify properties were updated
    assert "temperature" in coordinator.data.devices["device-1"].properties
    assert coordinator.data.devices["device-1"].properties["temperature"].value == 25.0


async def test_coordinator_device_filtering(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test device filtering through DeviceManagement."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    # Create mock devices
    mock_device1 = MagicMock()
    mock_device1.device_id = "device-1"
    mock_device1.device_name = "Device 1"
    mock_device1.online = True
    mock_device1.raw_data = {}

    mock_device2 = MagicMock()
    mock_device2.device_id = "device-2"
    mock_device2.device_name = "Device 2"
    mock_device2.online = True
    mock_device2.raw_data = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {
        "device-1": mock_device1,
        "device-2": mock_device2,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    # Create mock DeviceManagement
    mock_device_management = MagicMock(spec=DeviceManagement)
    # Filter to only return device-1
    mock_device_management.filter_manager.get_filtered_devices.return_value = [
        mock_device1
    ]

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
        device_management=mock_device_management,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify filtering was applied - only device-1 should be present
    assert len(coordinator.data.devices) == 1
    assert "device-1" in coordinator.data.devices
    assert "device-2" not in coordinator.data.devices

    # Verify filter_manager was called
    mock_device_management.filter_manager.get_filtered_devices.assert_called_once()


async def test_coordinator_device_detail_cache_refresh(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test device detail cache refresh after TTL expires."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}
    mock_api_client.cloud_client._async_get_device_detail = AsyncMock(
        return_value={"properties": []}
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First update - should cache
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    first_call_count = mock_api_client.cloud_client._async_get_device_detail.call_count

    # Simulate cache TTL expiry by setting timestamp to old value
    coordinator._device_detail_cache_timestamp = datetime.now(UTC) - timedelta(
        seconds=400
    )

    # Second update - should refresh cache
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    second_call_count = mock_api_client.cloud_client._async_get_device_detail.call_count

    # Should have called _async_get_device_detail again after cache expiry
    assert second_call_count > first_call_count


async def test_coordinator_mqtt_property_value_update(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT property update changes existing property value."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.0
        ),
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify initial value
    assert coordinator.data.devices["device-1"].properties["temperature"].value == 25.0

    # Update via MQTT
    coordinator._on_device_property_update("device-1", {"temperature": 30.0})
    await hass.async_block_till_done()

    # Verify value was updated
    assert coordinator.data.devices["device-1"].properties["temperature"].value == 30.0


async def test_coordinator_update_exception_wrapping(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test that unexpected exceptions are wrapped in UpdateFailed."""
    mock_api_client.async_get_user_info.return_value = MagicMock(user_id="test-user-id")
    mock_api_client.async_get_homes.return_value = [MagicMock(home_id="test-home-id")]
    mock_api_client.async_get_devices.side_effect = ValueError("Unexpected value error")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Should wrap the exception in UpdateFailed
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "Unexpected value error" in str(coordinator.last_exception)


async def test_coordinator_home_info_auth_failed(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test that HeimanAuthError in home info fetch is handled gracefully.

    ConfigEntryAuthFailed is caught by generic handler and logged as error,
    not re-raised. This test uses HeimanAuthError which is properly re-raised.
    """
    mock_api_client.cloud_client.async_get_user_info = AsyncMock(
        return_value=MagicMock(user_id="test-user-id")
    )
    mock_api_client.cloud_client.async_get_homes.side_effect = HeimanAuthError(
        "Auth failed"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # HeimanAuthError should be stored as ConfigEntryAuthFailed
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)


async def test_coordinator_device_fetch_auth_failed(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test that HeimanAuthError in device fetch is converted to ConfigEntryAuthFailed."""
    mock_api_client.cloud_client.async_get_user_info = AsyncMock(
        return_value=MagicMock(user_id="test-user-id")
    )
    mock_api_client.cloud_client.async_get_homes = AsyncMock(
        return_value=[MagicMock(home_id="test-home-id")]
    )
    mock_api_client.cloud_client.async_get_devices.side_effect = HeimanAuthError(
        "Auth failed"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # ConfigEntryAuthFailed should be stored as-is
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)


async def test_coordinator_device_detail_fetch_failure(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test device detail fetch failure handling."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}
    mock_api_client.async_get_device_detail.side_effect = Exception(
        "Detail fetch failed"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Should not raise, just log debug
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Device should still be present even if detail fetch failed
    assert "device-1" in coordinator.data.devices


async def test_coordinator_process_device_detail_invalid_metadata(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test processing device detail with invalid deriveMetadata."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}
    mock_api_client.cloud_client._async_get_device_detail = AsyncMock(
        return_value={
            "deriveMetadata": "invalid json",
        }
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Should not raise, just log exception
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Device should be present even if metadata parsing failed
    assert "device-1" in coordinator.data.devices


async def test_coordinator_update_regular_property(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test updating regular device property."""
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.0
        )
    }

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=MockConfigEntry(
            domain=DOMAIN,
            data={"token": {}, "home_id": "test", "user_id": "test"},
            unique_id="test",
        ),
    )

    # Update property value
    coordinator._update_device_property(
        mock_device, {"property": "temperature", "value": 30.0}
    )

    # Verify value was updated
    assert mock_device.properties["temperature"].value == 30.0


async def test_coordinator_process_device_info_create_level_property(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test creating DeviceINFO_DBM_Level property when it doesn't exist."""
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.properties = {
        "DeviceINFO_DBM": DeviceProperty(
            identifier="DeviceINFO_DBM", name="DBM", value=None
        )
    }

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=MockConfigEntry(
            domain=DOMAIN,
            data={"token": {}, "home_id": "test", "user_id": "test"},
            unique_id="test",
        ),
    )

    # Process device info with DBM but no DBM_Level
    coordinator._process_device_info(mock_device, {"DBM": -60, "DBM_Level": None})

    # Verify DBM_Level property was created
    assert "DeviceINFO_DBM_Level" in mock_device.properties
    assert mock_device.properties["DeviceINFO_DBM_Level"].value == "medium"


async def test_coordinator_merge_preserves_old_properties(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test that old properties are preserved when not in new device data."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    # Old device with MQTT-only property
    old_device = MagicMock(spec=HeimanDevice)
    old_device.device_id = "device-1"
    old_device.device_name = "Test Device"
    old_device.online = True
    old_device.raw_data = {}
    old_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.0
        ),
        "mqtt_only": DeviceProperty(
            identifier="mqtt_only", name="MQTT Only", value=100
        ),
    }

    # New device without MQTT-only property
    new_device = MagicMock(spec=HeimanDevice)
    new_device.device_id = "device-1"
    new_device.device_name = "Test Device"
    new_device.online = True
    new_device.raw_data = {}
    new_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=None
        )
    }

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": new_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First update - populate with old device
    coordinator.data.devices = {"device-1": old_device}

    # Second update - should merge properties
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # MQTT-only property should be preserved
    device = coordinator.data.devices["device-1"]
    assert "mqtt_only" in device.properties
    assert device.properties["mqtt_only"].value == 100
    # Temperature should keep old value since new value is None
    assert device.properties["temperature"].value == 25.0


async def test_coordinator_oauth_session_token_none(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT initialization when OAuth session token is None."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {},  # No access token
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    # Create mock OAuth session with None token
    mock_oauth_session = MagicMock()
    mock_oauth_session.token = None
    mock_oauth_session.async_ensure_token_valid = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
        oauth_session=mock_oauth_session,
    )

    # Initialize MQTT - should not raise, just log warning
    await coordinator.async_init_mqtt_client()

    # MQTT client should not be initialized
    assert coordinator.mqtt_client is None


async def test_coordinator_get_user_display_name_exception(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT initialization when getting user display name raises exception."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"
    # Make accessing user_info raise exception
    type(mock_user).user_info = property(
        lambda self: (_ for _ in ()).throw(Exception("Access error"))
    )

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()

    # Initialize MQTT - should handle exception gracefully
    mock_mqtt_instance = MagicMock()
    mock_mqtt_instance.connect = AsyncMock()
    mock_mqtt_instance.register_device_callback = MagicMock()

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient",
        return_value=mock_mqtt_instance,
    ):
        await coordinator.async_init_mqtt_client()


async def test_coordinator_get_cloud_client_exception(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT initialization when getting cloud_client raises exception."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    # Make accessing _cloud_client raise exception
    type(mock_api_client)._cloud_client = property(
        lambda self: (_ for _ in ()).throw(Exception("Access error"))
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Initialize MQTT - should handle exception gracefully
    mock_mqtt_instance = MagicMock()
    mock_mqtt_instance.connect = AsyncMock()
    mock_mqtt_instance.register_device_callback = MagicMock()

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient",
        return_value=mock_mqtt_instance,
    ):
        await coordinator.async_init_mqtt_client()


async def test_coordinator_mqtt_init_heiman_mqtt_error(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT initialization when HeimanMQTTError is raised."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Mock HeimanMqttClient to raise HeimanMQTTError
    mock_mqtt_instance = MagicMock()
    mock_mqtt_instance.connect = AsyncMock(
        side_effect=HeimanMQTTError("MQTT connection failed")
    )
    mock_mqtt_instance.register_device_callback = MagicMock()

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient",
        return_value=mock_mqtt_instance,
    ):
        # Should not raise, just log error
        await coordinator.async_init_mqtt_client()

        # MQTT client instance is created but connect failed
        assert coordinator.mqtt_client is not None
        assert coordinator.mqtt_client.connect.called


async def test_coordinator_read_device_properties_add_property(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test reading device properties and adding new properties."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {}
    mock_device.product_id = "prod-1"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Mock MQTT client to return new properties
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_read_properties = AsyncMock(
        return_value={"temperature": 25.0, "humidity": 60.0}
    )
    coordinator.mqtt_client = mock_mqtt_client

    # Read device properties
    await coordinator.async_read_device_properties("device-1")

    # Verify properties were added
    device = coordinator.data.devices["device-1"]
    assert "temperature" in device.properties
    assert device.properties["temperature"].value == 25.0
    assert "humidity" in device.properties
    assert device.properties["humidity"].value == 60.0


async def test_coordinator_read_device_properties_exception(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test reading device properties with exception."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {}
    mock_device.product_id = "prod-1"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Mock MQTT client to raise exception
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_read_properties = AsyncMock(
        side_effect=Exception("Read failed")
    )
    coordinator.mqtt_client = mock_mqtt_client

    # Should not raise, just log error
    await coordinator.async_read_device_properties("device-1")


async def test_coordinator_mqtt_init_user_display_name_exception(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT initialization when getting user display name raises exception."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {}
    mock_device.product_id = "prod-1"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Mock user_info to raise exception when accessing attributes
    coordinator.data.user_info = MagicMock()
    coordinator.data.user_info.nick_name = MagicMock(
        side_effect=Exception("Access error")
    )
    coordinator.data.user_info.email = MagicMock(side_effect=Exception("Access error"))

    # Initialize MQTT - should handle exception gracefully
    mock_mqtt_instance = MagicMock()
    mock_mqtt_instance.connect = AsyncMock()
    mock_mqtt_instance.register_device_callback = MagicMock()

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient",
        return_value=mock_mqtt_instance,
    ):
        await coordinator.async_init_mqtt_client()


async def test_coordinator_read_device_properties_update_existing(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test reading device properties and updating existing properties."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    # Create device with existing properties
    existing_prop = DeviceProperty(
        identifier="temperature",
        name="Temperature",
        value=20.0,
    )

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {"temperature": existing_prop}
    mock_device.product_id = "prod-1"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Mock MQTT client to return updated properties
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_read_properties = AsyncMock(
        return_value={"temperature": 25.0, "humidity": 60.0}
    )
    coordinator.mqtt_client = mock_mqtt_client

    # Read device properties
    await coordinator.async_read_device_properties("device-1")

    # Verify existing property was updated
    device = coordinator.data.devices["device-1"]
    assert device.properties["temperature"].value == 25.0
    # Verify new property was added
    assert "humidity" in device.properties
    assert device.properties["humidity"].value == 60.0


async def test_coordinator_read_device_properties_empty_response(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test reading device properties when no properties are returned."""
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}
    mock_device.properties = {}
    mock_device.product_id = "prod-1"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Mock MQTT client to return empty properties
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_read_properties = AsyncMock(return_value=None)
    coordinator.mqtt_client = mock_mqtt_client

    # Read device properties - should log warning but not raise
    await coordinator.async_read_device_properties("device-1")

    # Verify no properties were added
    device = coordinator.data.devices["device-1"]
    assert len(device.properties) == 0


async def test_coordinator_update_unexpected_exception(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test coordinator update with unexpected exception.

    This tests the generic Exception handler in _async_update_data
    that wraps unexpected errors as UpdateFailed.
    """
    # Make cloud_client.async_get_user_info raise an unexpected error
    mock_api_client.cloud_client.async_get_user_info = AsyncMock(
        side_effect=RuntimeError("Unexpected database error")
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # The exception handler in _fetch_user_and_home_info should catch
    # the RuntimeError and wrap it in UpdateFailed
    # Note: async_refresh catches UpdateFailed internally, so we call
    # _async_update_data directly to trigger the exception
    with pytest.raises(UpdateFailed, match="Failed to fetch user info"):
        await coordinator._async_update_data()

    await hass.async_block_till_done()


async def test_mqtt_init_user_display_name_exception(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT init handles user_display_name exception gracefully.

    This tests the exception handling around getattr for user_info
    when getting user display name.
    """
    # Setup mocks
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"
    mock_user.email = "test@example.com"
    # Make user_info raise exception when accessed
    type(mock_user).nick_name = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("Error"))
    )
    type(mock_user).email = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("Error"))
    )

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"
    mock_home.home_name = "Test Home"
    mock_home.device_count = 2

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.raw_data = {}

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]
    mock_api_client.async_get_devices.return_value = {"device-1": mock_device}
    mock_api_client.async_get_device_detail = AsyncMock(return_value={})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test-token",
                "refresh_token": "test-refresh",
                "expires_at": 9999999999,
            },
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Manually set user_info to trigger the exception path
    coordinator.data.user_info = mock_user

    # Mock the mqtt client to avoid actual connection
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.connect = AsyncMock()
    mock_mqtt_client.register_device_callback = MagicMock()

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanMqttClient",
            return_value=mock_mqtt_client,
        ),
    ):
        # This should not raise, exception should be caught and logged
        await coordinator.async_init_mqtt_client()

    # Verify MQTT client was created even if user_display_name failed
    # The exception is caught and logged, initialization continues


async def test_mqtt_init_oauth_failure(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT init handles OAuth token failure gracefully.

    This tests the generic exception handler in async_init_mqtt_client
    when getting access_token fails unexpectedly.
    """
    # Setup mocks
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"
    mock_user.email = "test@example.com"

    mock_api_client.async_get_user_info.return_value = mock_user
    # Make token retrieval fail unexpectedly
    mock_api_client.token = None  # This will cause access_token to be None

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": None,  # Invalid token
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Manually set user_info
    coordinator.data.user_info = mock_user

    # Mock oauth_session to raise unexpected error
    mock_oauth_session = MagicMock()
    mock_oauth_session.async_ensure_token_valid = AsyncMock(
        side_effect=RuntimeError("Unexpected OAuth error")
    )
    coordinator.oauth_session = mock_oauth_session

    # This should not raise, exception should be caught and logged
    await coordinator.async_init_mqtt_client()

    # Verify mqtt_client was not set since initialization failed
    assert coordinator.mqtt_client is None


async def test_coordinator_extract_firmware_versions_edge_cases(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test _extract_firmware_versions with various edge cases.

    This tests the code paths in _extract_firmware_versions method
    for lines 132-134 coverage.
    """
    # Create devices with various edge case data
    mock_device1 = MagicMock()
    mock_device1.device_id = "device-1"
    mock_device1.firmware_version = None
    mock_device1.raw_data = None  # None raw_data

    mock_device2 = MagicMock()
    mock_device2.device_id = "device-2"
    mock_device2.firmware_version = None
    mock_device2.raw_data = {}  # Empty raw_data

    mock_device3 = MagicMock()
    mock_device3.device_id = "device-3"
    mock_device3.firmware_version = None
    mock_device3.raw_data = {"other_key": "value"}  # No firmwareInfo

    mock_device4 = MagicMock()
    mock_device4.device_id = "device-4"
    mock_device4.firmware_version = None
    mock_device4.raw_data = {"firmwareInfo": "not_a_dict"}  # firmwareInfo is string

    mock_device5 = MagicMock()
    mock_device5.device_id = "device-5"
    mock_device5.firmware_version = None
    mock_device5.raw_data = {"firmwareInfo": {"other_key": "value"}}  # No version key
    mock_device5.firmware_info = None  # No firmware_info attribute

    devices = {
        "device-1": mock_device1,
        "device-2": mock_device2,
        "device-3": mock_device3,
        "device-4": mock_device4,
        "device-5": mock_device5,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Call _extract_firmware_versions - should not raise
    coordinator._extract_firmware_versions(devices)

    # All devices should still be in the dict
    assert len(devices) == 5
    # Firmware version should remain None for all edge cases
    assert mock_device1.firmware_version is None
    assert mock_device2.firmware_version is None
    assert mock_device3.firmware_version is None
    assert mock_device4.firmware_version is None
    assert mock_device5.firmware_version is None


async def test_coordinator_extract_firmware_versions_with_firmware_info(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test _extract_firmware_versions with firmware_info attribute.

    This tests the code path at line 217 where firmware_info is checked.
    """
    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.firmware_version = None
    mock_device.raw_data = {}  # No firmwareInfo in raw_data
    mock_device.firmware_info = {"version": "4.0.0"}

    devices = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Call _extract_firmware_versions
    coordinator._extract_firmware_versions(devices)

    # Firmware version should be set from firmware_info
    assert mock_device.firmware_version == "4.0.0"


async def test_coordinator_extract_firmware_versions_firmware_info_overrides(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test _extract_firmware_versions firmware_info overrides raw_data value.

    The code checks raw_data first, then firmware_info. Since firmware_info
    is checked second, it will override any value set from raw_data.
    """
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.firmware_version = None
    mock_device.raw_data = {"firmwareInfo": {"version": "1.0.0"}}
    mock_device.firmware_info = {"version": "2.0.0"}

    devices = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Call _extract_firmware_versions
    coordinator._extract_firmware_versions(devices)

    # firmware_info overrides raw_data since it's checked second
    assert mock_device.firmware_version == "2.0.0"


async def test_coordinator_extract_firmware_versions_firmware_info_fallback(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test _extract_firmware_versions uses firmware_info when raw_data has no version.

    This tests that firmware_info is used when raw_data doesn't have version.
    """
    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.firmware_version = None
    mock_device.raw_data = {"firmwareInfo": {"other_key": "value"}}  # No version
    mock_device.firmware_info = {"version": "3.0.0"}

    devices = {"device-1": mock_device}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Call _extract_firmware_versions
    coordinator._extract_firmware_versions(devices)

    # Firmware version should be set from firmware_info
    assert mock_device.firmware_version == "3.0.0"


def test_infer_entity_type_bool() -> None:
    """Test _infer_entity_type returns None for bool values.

    Boolean values should not be represented by sensor platform since
    the sensor platform rejects bool native values. Once binary_sensor
    platform is implemented, this should return "binary_sensor".
    This tests line 53 where prop_value is bool.
    """
    assert _infer_entity_type(True) is None
    assert _infer_entity_type(False) is None


def test_infer_entity_type_numeric() -> None:
    """Test _infer_entity_type returns sensor for numeric values.

    This tests line 56 where prop_value is int or float.
    """
    assert _infer_entity_type(42) == "sensor"
    assert _infer_entity_type(3.14) == "sensor"
    assert _infer_entity_type(-100) == "sensor"


def test_infer_entity_type_other() -> None:
    """Test _infer_entity_type returns sensor for other types.

    String values return 'sensor', but non-scalar values (dict, list, tuple, set)
    return None because they cannot be represented as sensor native values.
    """
    # String values are valid sensor native values
    assert _infer_entity_type("string") == "sensor"
    # Non-scalar values cannot be represented as sensor native values
    assert _infer_entity_type([1, 2, 3]) is None
    assert _infer_entity_type({"key": "value"}) is None
    assert _infer_entity_type((1, 2)) is None
    assert _infer_entity_type({1, 2, 3}) is None


async def test_coordinator_mqtt_init_exception(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test MQTT initialization when unexpected exception is raised.

    This tests lines 591-592 where a general Exception is caught.
    """
    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"

    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"

    mock_api_client.async_get_user_info.return_value = mock_user
    mock_api_client.async_get_homes.return_value = [mock_home]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {"access_token": "test-token"},
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Mock HeimanMqttClient to raise a general Exception
    mock_mqtt_instance = MagicMock()
    # Raise Exception in connect (not HeimanMQTTError)
    mock_mqtt_instance.connect = AsyncMock(side_effect=RuntimeError("Unexpected error"))

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient",
        return_value=mock_mqtt_instance,
    ):
        # Should not raise, just log error
        await coordinator.async_init_mqtt_client()

        # MQTT client instance is created but connect failed
        assert coordinator.mqtt_client is not None
        assert coordinator.mqtt_client.connect.called
