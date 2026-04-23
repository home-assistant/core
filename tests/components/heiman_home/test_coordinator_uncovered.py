"""Tests for Heiman Home coordinator uncovered code paths."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from heimanconnect.cloud_client_wrapper import HeimanCloudClientWrapper
from heimanconnect.models import HeimanDevice, HeimanHome, HeimanUser

from homeassistant.components.heiman_home.const import CONF_HOME_ID
from homeassistant.components.heiman_home.coordinator import (
    DeviceProperty,
    HeimanData,
    HeimanDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_coordinator_update_data_success(hass: HomeAssistant) -> None:
    """Test a successful coordinator update sets the timestamp and stores data."""
    # Create mock config entry
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    # Create mock API client
    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    # Mock user info
    mock_user_info = MagicMock(spec=HeimanUser)
    mock_user_info.user_id = "test-user"
    mock_user_info.email = "test@example.com"

    # Mock home info
    mock_home_info = MagicMock(spec=HeimanHome)
    mock_home_info.home_id = "test-home-id"
    mock_home_info.home_name = "Test Home"

    # Mock devices
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_type = "sensor"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}
    mock_device.raw_data = {}
    mock_device.firmware_version = None

    mock_cloud_wrapper.async_get_user_info = AsyncMock(return_value=mock_user_info)
    mock_cloud_wrapper.async_get_homes = AsyncMock(return_value=[mock_home_info])
    mock_cloud_wrapper.async_get_devices = AsyncMock(
        return_value={"device-1": mock_device}
    )
    mock_cloud_wrapper._async_get_device_detail = AsyncMock(
        return_value={"firmwareInfo": {"version": "1.0.0"}, "deriveMetadata": "[]"}
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        config_entry=config_entry,
        api_client=mock_api_client,
    )

    # Perform update
    result = await coordinator._async_update_data()

    # Verify last_update was set
    assert result.last_update is not None
    assert isinstance(result.last_update, datetime)

    # Verify data was returned
    assert result is coordinator.data
    assert "device-1" in result.devices


async def test_coordinator_fetch_devices_without_filtering(hass: HomeAssistant) -> None:
    """Test fetching devices when device_management is None."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_type = "sensor"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}
    mock_device.raw_data = {}
    mock_device.firmware_version = None

    mock_cloud_wrapper.async_get_user_info = AsyncMock(return_value=None)
    mock_cloud_wrapper.async_get_homes = AsyncMock(return_value=[])
    mock_cloud_wrapper.async_get_devices = AsyncMock(
        return_value={"device-1": mock_device}
    )
    mock_cloud_wrapper._async_get_device_detail = AsyncMock(
        return_value={"firmwareInfo": {}, "deriveMetadata": "[]"}
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        config_entry=config_entry,
        api_client=mock_api_client,
    )

    # Set initial data to avoid None checks
    coordinator.data = HeimanData(
        devices={},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Fetch devices - device_management is None so all devices are fetched
    await coordinator._fetch_and_process_devices("test-home-id")

    # Verify devices were fetched without filtering
    assert "device-1" in coordinator.data.devices


async def test_coordinator_update_device_details_cache_hit(hass: HomeAssistant) -> None:
    """Test device detail update with cache hit avoids API calls."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_type = "sensor"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}
    mock_device.raw_data = {}
    mock_device.firmware_version = None

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        config_entry=config_entry,
        api_client=mock_api_client,
    )

    # Pre-populate cache
    cached_detail = {"firmwareInfo": {"version": "2.0.0"}, "deriveMetadata": "[]"}
    coordinator._device_detail_cache["device-1"] = cached_detail
    coordinator._device_detail_cache_timestamp = datetime.now(UTC)

    devices = {"device-1": mock_device}

    # This should use cached data without making API calls
    await coordinator._update_device_details(devices)

    # Verify cache was used (no API call made)
    mock_cloud_wrapper._async_get_device_detail.assert_not_called()


async def test_coordinator_process_device_detail_with_derive_metadata(
    hass: HomeAssistant,
) -> None:
    """Test processing device detail with invalid deriveMetadata JSON."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_type = "sensor"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}
    mock_device.raw_data = {}
    mock_device.firmware_version = None

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        config_entry=config_entry,
        api_client=mock_api_client,
    )

    # Test with invalid JSON in deriveMetadata (triggers exception handling)
    device_detail = {
        "firmwareInfo": {"version": "1.0.0"},
        "deriveMetadata": "invalid json {{{",
    }

    # This should catch the exception and log it
    coordinator._process_device_detail(mock_device, device_detail)

    # Device should still be processed (exception caught)
    assert mock_device.firmware_version == "1.0.0"


async def test_coordinator_update_device_property_early_return(
    hass: HomeAssistant,
) -> None:
    """Test property update skips when prop_id or value is missing."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_type = "sensor"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}
    mock_device.raw_data = {}
    mock_device.firmware_version = None

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        config_entry=config_entry,
        api_client=mock_api_client,
    )

    # Test with missing prop_id
    prop_item_no_id = {"value": "test"}
    coordinator._update_device_property(mock_device, prop_item_no_id)

    # Test with None value
    prop_item_no_value = {"identifier": "test", "value": None}
    coordinator._update_device_property(mock_device, prop_item_no_value)

    # No properties should be added
    assert len(mock_device.properties) == 0


async def test_coordinator_process_device_info(hass: HomeAssistant) -> None:
    """Test processing DeviceINFO nested structure."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_type = "sensor"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "DeviceINFO_DBM": DeviceProperty(
            identifier="DeviceINFO_DBM",
            name="Signal Strength",
            value=-65,
            readable=True,
            entity="sensor",
        )
    }
    mock_device.raw_data = {}
    mock_device.firmware_version = None

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        config_entry=config_entry,
        api_client=mock_api_client,
    )

    # Test DeviceINFO processing with DBM level
    device_info = {"DBM": -65, "DBM_Level": "good"}

    prop_item = {"property": "DeviceINFO", "value": device_info}

    coordinator._update_device_property(mock_device, prop_item)

    # Verify DeviceINFO_DBM_Level was created/updated
    assert "DeviceINFO_DBM_Level" in mock_device.properties


async def test_coordinator_merge_device_states_keep_runtime_properties(
    hass: HomeAssistant,
) -> None:
    """Test merging device states preserves runtime-discovered properties."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    # Old device with runtime property
    old_device = MagicMock(spec=HeimanDevice)
    old_device.device_id = "device-1"
    old_device.device_type = "sensor"
    old_device.device_name = "Test Device"
    old_device.online = True
    old_device.properties = {
        "mqtt_only_field": DeviceProperty(
            identifier="mqtt_only_field",
            name="MQTT Field",
            value="runtime_value",
            readable=True,
            entity="sensor",
        )
    }
    old_device.raw_data = {}
    old_device.firmware_version = "1.0.0"

    # New device without the runtime property
    new_device = MagicMock(spec=HeimanDevice)
    new_device.device_id = "device-1"
    new_device.device_type = "sensor"
    new_device.device_name = "Test Device"
    new_device.online = True
    new_device.properties = {}  # Empty - doesn't have mqtt_only_field
    new_device.raw_data = {}
    new_device.firmware_version = "1.0.0"

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        config_entry=config_entry,
        api_client=mock_api_client,
    )

    # Set initial data
    coordinator.data = HeimanData(
        devices={"device-1": old_device},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Merge states - should keep runtime property
    coordinator._merge_device_states({"device-1": new_device})

    # Verify runtime property was preserved
    merged_device = coordinator.data.devices["device-1"]
    assert "mqtt_only_field" in merged_device.properties
    assert merged_device.properties["mqtt_only_field"].value == "runtime_value"


async def test_coordinator_get_online_devices(hass: HomeAssistant) -> None:
    """Test retrieving only online devices from coordinator data."""

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    online_device = MagicMock(spec=HeimanDevice)
    online_device.device_id = "device-1"
    online_device.device_type = "sensor"
    online_device.device_name = "Online Device"
    online_device.online = True
    online_device.properties = {}
    online_device.raw_data = {}
    online_device.firmware_version = None

    offline_device = MagicMock(spec=HeimanDevice)
    offline_device.device_id = "device-2"
    offline_device.device_type = "sensor"
    offline_device.device_name = "Offline Device"
    offline_device.online = False
    offline_device.properties = {}
    offline_device.raw_data = {}
    offline_device.firmware_version = None

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        config_entry=config_entry,
        api_client=mock_api_client,
    )

    coordinator.data = HeimanData(
        devices={
            "device-1": online_device,
            "device-2": offline_device,
        },
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Test get_online_devices
    online_devices = coordinator.get_online_devices()
    assert len(online_devices) == 1
    assert online_devices[0].device_id == "device-1"

    # Test get_device
    device = coordinator.get_device("device-1")
    assert device is not None
    assert device.device_id == "device-1"

    # Test get_device with non-existent ID
    device_none = coordinator.get_device("non-existent")
    assert device_none is None
