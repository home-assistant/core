"""Tests for Heiman Home coordinator remaining uncovered code."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from heimanconnect.cloud_client_wrapper import HeimanCloudClientWrapper
from heimanconnect.models import HeimanDevice

from homeassistant.components.heiman_home.const import CONF_HOME_ID
from homeassistant.components.heiman_home.coordinator import (
    DeviceProperty,
    HeimanData,
    HeimanDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_coordinator_process_device_detail_cache_hit_and_process(
    hass: HomeAssistant,
) -> None:
    """Test device detail processing with cache hit (line 318)."""
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
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Pre-populate cache with device detail
    cached_detail = {
        "firmwareInfo": {"version": "2.0.0"},
        "deriveMetadata": "[]",
    }
    coordinator._device_detail_cache["device-1"] = cached_detail
    coordinator._device_detail_cache_timestamp = datetime.now(UTC)

    devices = {"device-1": mock_device}

    # This should use cached data and call _process_device_detail (line 318)
    await coordinator._update_device_details(devices)

    # Verify cache was used (no API call made)
    mock_cloud_wrapper._async_get_device_detail.assert_not_called()
    # Verify firmware version was updated
    assert mock_device.firmware_version == "2.0.0"


async def test_coordinator_process_device_detail_with_invalid_json(
    hass: HomeAssistant,
) -> None:
    """Test processing device detail with invalid JSON in deriveMetadata (lines 342-343)."""
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
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Test with invalid JSON in deriveMetadata (triggers exception at lines 342-343)
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
    """Test property update with missing prop_id or value (line 359)."""
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
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Test with empty prop_id (line 355 returns early)
    prop_item_no_id = {"value": "test"}
    coordinator._update_device_property(mock_device, prop_item_no_id)

    # Test with None value (line 355 returns early)
    prop_item_no_value = {"identifier": "test", "value": None}
    coordinator._update_device_property(mock_device, prop_item_no_value)

    # No properties should be added
    assert len(mock_device.properties) == 0


async def test_coordinator_process_device_info_creates_dbm_level(
    hass: HomeAssistant,
) -> None:
    """Test processing DeviceINFO creates DBM_Level property (line 411)."""
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
    # Don't include DeviceINFO_DBM_Level - let it be created
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
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Test DeviceINFO processing with DBM level
    device_info = {"DBM": -65, "DBM_Level": "good"}

    prop_item = {"property": "DeviceINFO", "value": device_info}

    coordinator._update_device_property(mock_device, prop_item)

    # Verify DeviceINFO_DBM_Level was created (line 411-421)
    assert "DeviceINFO_DBM_Level" in mock_device.properties
    assert mock_device.properties["DeviceINFO_DBM_Level"].value == "good"


async def test_coordinator_merge_device_states_keeps_runtime_properties(
    hass: HomeAssistant,
) -> None:
    """Test merging device states keeps runtime properties (lines 442-443)."""
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
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Set initial data
    coordinator.data = HeimanData(
        devices={"device-1": old_device},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Merge states - should keep runtime property (lines 442-443)
    coordinator._merge_device_states({"device-1": new_device})

    # Verify runtime property was preserved
    merged_device = coordinator.data.devices["device-1"]
    assert "mqtt_only_field" in merged_device.properties
    assert merged_device.properties["mqtt_only_field"].value == "runtime_value"


async def test_coordinator_read_device_properties_no_properties_returned(
    hass: HomeAssistant,
) -> None:
    """Test reading device properties when no properties returned (line 678)."""
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
    mock_device.product_id = "test-product"

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Set up minimal data
    coordinator.data = HeimanData(
        devices={"device-1": mock_device},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Mock MQTT client that returns empty properties
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_read_properties = AsyncMock(return_value={})
    coordinator.mqtt_client = mock_mqtt_client

    # Read properties - should log warning at line 678
    await coordinator.async_read_device_properties("device-1")

    # Verify MQTT was called
    mock_mqtt_client.async_read_properties.assert_called_once()


async def test_coordinator_get_online_devices(hass: HomeAssistant) -> None:
    """Test getting online devices (line 691)."""
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
        api_client=mock_api_client,
        config_entry=config_entry,
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

    # Test get_online_devices (line 691)
    online_devices = coordinator.get_online_devices()
    assert len(online_devices) == 1
    assert online_devices[0].device_id == "device-1"


async def test_coordinator_get_device_property_value(hass: HomeAssistant) -> None:
    """Test getting device property value (lines 707-711)."""
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
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            readable=True,
            entity="sensor",
        )
    }
    mock_device.raw_data = {}
    mock_device.firmware_version = None

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(
        devices={"device-1": mock_device},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Test getting existing property (lines 707-711)
    value = coordinator.get_device_property("device-1", "temperature")
    assert value == 25.5

    # Test getting non-existent property (line 708-709)
    value_none = coordinator.get_device_property("device-1", "humidity")
    assert value_none is None

    # Test getting property from non-existent device (line 704-705)
    value_none_device = coordinator.get_device_property("non-existent", "temperature")
    assert value_none_device is None
