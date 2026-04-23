"""Additional tests for coordinator remaining uncovered lines."""

from unittest.mock import AsyncMock, MagicMock, patch

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


async def test_coordinator_process_device_info_updates_existing_dbm_level(
    hass: HomeAssistant,
) -> None:
    """Test processing DeviceINFO updates existing DBM_Level property (line 411)."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    # Create device with existing DBM_Level property
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
        ),
        "DeviceINFO_DBM_Level": DeviceProperty(
            identifier="DeviceINFO_DBM_Level",
            name="DBM Level",
            value="medium",  # Existing value
            readable=True,
            entity="sensor",
        ),
    }
    mock_device.raw_data = {}
    mock_device.firmware_version = None

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Test updating existing DBM_Level (should hit line 411)
    device_info = {"DBM": -45, "DBM_Level": "strong"}
    prop_item = {"property": "DeviceINFO", "value": device_info}

    coordinator._update_device_property(mock_device, prop_item)

    # Verify DBM_Level was updated (not recreated)
    assert mock_device.properties["DeviceINFO_DBM_Level"].value == "strong"
    # Should still be the same object reference
    assert "DeviceINFO_DBM_Level" in mock_device.properties


async def test_coordinator_get_device(hass: HomeAssistant) -> None:
    """Test getting device by ID (line 466)."""
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

    coordinator.data = HeimanData(
        devices={"device-1": mock_device},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Test getting existing device (line 466)
    device = coordinator.get_device("device-1")
    assert device is not None
    assert device.device_id == "device-1"

    # Test getting non-existent device
    device_none = coordinator.get_device("non-existent")
    assert device_none is None


async def test_coordinator_get_devices_by_type(hass: HomeAssistant) -> None:
    """Test getting devices by type (line 485)."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    sensor_device = MagicMock(spec=HeimanDevice)
    sensor_device.device_id = "device-1"
    sensor_device.device_type = "sensor"
    sensor_device.device_name = "Sensor"
    sensor_device.online = True
    sensor_device.properties = {}
    sensor_device.raw_data = {}
    sensor_device.firmware_version = None

    switch_device = MagicMock(spec=HeimanDevice)
    switch_device.device_id = "device-2"
    switch_device.device_type = "switch"
    switch_device.device_name = "Switch"
    switch_device.online = True
    switch_device.properties = {}
    switch_device.raw_data = {}
    switch_device.firmware_version = None

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(
        devices={
            "device-1": sensor_device,
            "device-2": switch_device,
        },
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Test get_devices_by_type (line 485)
    sensors = coordinator.get_devices_by_type("sensor")
    assert len(sensors) == 1
    assert sensors[0].device_type == "sensor"

    switches = coordinator.get_devices_by_type("switch")
    assert len(switches) == 1
    assert switches[0].device_type == "switch"

    lights = coordinator.get_devices_by_type("light")
    assert len(lights) == 0


async def test_coordinator_mqtt_init_no_token(hass: HomeAssistant) -> None:
    """Test MQTT init when no token available (lines 534-536)."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(
        devices={},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Mock OAuth2 session that raises exception
    mock_session = MagicMock()
    mock_session.token = None
    mock_session.async_ensure_token_valid = AsyncMock(
        side_effect=Exception("Session error")
    )
    coordinator.oauth_session = mock_session

    # Initialize MQTT - should handle exception gracefully (lines 534-536)
    await coordinator.async_init_mqtt_client()

    # MQTT client should not be created due to missing token
    assert coordinator.mqtt_client is None


async def test_coordinator_mqtt_init_no_user_display_name(hass: HomeAssistant) -> None:
    """Test MQTT init when user display name unavailable (lines 557-558)."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        "user_id": "test-user",
        "token": {"access_token": "test-token"},
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Set user_info to None to trigger the exception path
    coordinator.data = HeimanData(
        devices={},
        user_info=None,  # No user info
        home_info=None,
        errors={},
        last_update=None,
    )

    # Mock OAuth2 session
    mock_session = MagicMock()
    mock_session.token = {"access_token": "test-token"}
    mock_session.async_ensure_token_valid = AsyncMock()
    coordinator.oauth_session = mock_session

    # Mock MQTT client creation
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        # This should handle the None user_info gracefully (lines 557-558)
        await coordinator.async_init_mqtt_client()

        # Verify MQTT client was created despite missing user display name
        mock_mqtt_class.assert_called_once()
        call_kwargs = mock_mqtt_class.call_args
        assert call_kwargs[1]["user_display_name"] is None


async def test_coordinator_mqtt_init_cloud_client_exception(
    hass: HomeAssistant,
) -> None:
    """Test MQTT init handles cloud_client access exception (lines 566-567)."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        "user_id": "test-user",
        "token": {"access_token": "test-token"},
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    # Make accessing _wrapper raise an exception
    type(mock_api_client).cloud_client = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("Not initialized"))
    )
    mock_api_client._wrapper = None

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(
        devices={},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Mock OAuth2 session
    mock_session = MagicMock()
    mock_session.token = {"access_token": "test-token"}
    mock_session.async_ensure_token_valid = AsyncMock()
    coordinator.oauth_session = mock_session

    # Mock MQTT client creation
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        # This should handle cloud_client exception gracefully (lines 566-567)
        await coordinator.async_init_mqtt_client()

        # Verify MQTT client was still created with cloud_client=None
        mock_mqtt_class.assert_called_once()
        call_kwargs = mock_mqtt_class.call_args
        assert call_kwargs[1]["cloud_client"] is None


async def test_coordinator_read_device_properties_with_returned_properties(
    hass: HomeAssistant,
) -> None:
    """Test reading device properties with returned data (lines 655-676)."""
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
            value=20.0,
            readable=True,
            entity="sensor",
        )
    }
    mock_device.raw_data = {}
    mock_device.firmware_version = None
    mock_device.product_id = "test-product"

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

    # Mock MQTT client that returns properties
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_read_properties = AsyncMock(
        return_value={"temperature": 25.5, "humidity": 60}
    )
    coordinator.mqtt_client = mock_mqtt_client

    # Read properties - should update device and trigger async_set_updated_data
    await coordinator.async_read_device_properties("device-1")

    # Verify properties were updated
    assert mock_device.properties["temperature"].value == 25.5
    # New property should be added
    assert "humidity" in mock_device.properties
    assert mock_device.properties["humidity"].value == 60


async def test_coordinator_mqtt_init_general_exception(hass: HomeAssistant) -> None:
    """Test MQTT init handles general exceptions (lines 589-590)."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        "user_id": "test-user",
        "token": {"access_token": "test-token"},
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(
        devices={},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Mock OAuth2 session
    mock_session = MagicMock()
    mock_session.token = {"access_token": "test-token"}
    mock_session.async_ensure_token_valid = AsyncMock()
    coordinator.oauth_session = mock_session

    # Mock MQTT client that raises exception during connect
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        mock_mqtt_class.return_value = mock_mqtt_instance

        # This should handle the exception gracefully (lines 589-590)
        await coordinator.async_init_mqtt_client()

        # MQTT client should be cleared after failure so future calls can retry
        assert coordinator.mqtt_client is None


async def test_coordinator_mqtt_init_already_initialized(hass: HomeAssistant) -> None:
    """Test MQTT init when already initialized (line 514)."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(
        devices={},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Set mqtt_client to simulate already initialized
    coordinator.mqtt_client = MagicMock()

    # Call async_init_mqtt_client - should return early (line 514)
    await coordinator.async_init_mqtt_client()

    # Verify it returned early without doing anything
    assert coordinator.mqtt_client is not None


async def test_coordinator_mqtt_init_token_none_after_validation(
    hass: HomeAssistant,
) -> None:
    """Test MQTT init when token is None after validation (lines 533-534)."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(
        devices={},
        user_info=None,
        home_info=None,
        errors={},
        last_update=None,
    )

    # Mock OAuth2 session with token=None after validation
    mock_session = MagicMock()
    mock_session.token = None  # Token is None even after validation
    mock_session.async_ensure_token_valid = AsyncMock()
    coordinator.oauth_session = mock_session

    # Initialize MQTT - should log debug message and return (lines 533-534)
    await coordinator.async_init_mqtt_client()

    # MQTT client should not be created
    assert coordinator.mqtt_client is None
