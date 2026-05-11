"""Tests for coordinator coverage gaps - targeting 100% coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import (
    HeimanApiError,
    HeimanAuthError,
    HeimanConnectionError,
    HeimanMQTTError,
)
from heimanconnect.cloud_client_wrapper import HeimanCloudClientWrapper
from heimanconnect.models import DeviceProperty as SDKDeviceProperty, HeimanDevice
import pytest

from homeassistant.components.heiman_home.const import CONF_HOME_ID, CONF_USER_ID
from homeassistant.components.heiman_home.coordinator import (
    HeimanData,
    HeimanDataUpdateCoordinator,
    _async_call_cleanup_method,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_async_call_cleanup_method_with_none_method(hass: HomeAssistant) -> None:
    """Test _async_call_cleanup_method when method is None."""
    mock_target = MagicMock()
    # Set the attribute on this mock instance to trigger the continue path
    mock_target.nonexistent = None

    # This should skip the None method and continue
    await _async_call_cleanup_method(mock_target, ("nonexistent",))


async def test_async_call_cleanup_method_sync_method(hass: HomeAssistant) -> None:
    """Test _async_call_cleanup_method with sync method."""
    mock_target = MagicMock()
    mock_target.close = MagicMock(return_value=None)  # Sync method

    # Should call the sync method without awaiting
    await _async_call_cleanup_method(mock_target, ("close", "async_close"))
    mock_target.close.assert_called_once()


async def test_coordinator_async_update_data_no_home_id(hass: HomeAssistant) -> None:
    """Test _async_update_data raises UpdateFailed when home_id missing."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {}  # No CONF_HOME_ID
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Should raise UpdateFailed
    with pytest.raises(UpdateFailed, match="Home ID not found"):
        await coordinator._async_update_data()


async def test_coordinator_fetch_user_info_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test _fetch_user_and_home_info handles connection error."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Simulate connection error
    mock_cloud_wrapper.async_get_user_info = AsyncMock(
        side_effect=HeimanConnectionError("Connection failed")
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Should raise UpdateFailed
    with pytest.raises(UpdateFailed, match="Connection error"):
        await coordinator._fetch_user_and_home_info()


async def test_coordinator_fetch_user_info_general_exception(
    hass: HomeAssistant,
) -> None:
    """Test _fetch_user_and_home_info handles general exception."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Simulate general exception
    mock_cloud_wrapper.async_get_user_info = AsyncMock(
        side_effect=RuntimeError("Unexpected error")
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Should raise UpdateFailed
    with pytest.raises(UpdateFailed, match="Failed to fetch user info"):
        await coordinator._fetch_user_and_home_info()


async def test_coordinator_fetch_home_info_exception(hass: HomeAssistant) -> None:
    """Test _fetch_user_and_home_info handles home info exception."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # User info succeeds
    mock_user = MagicMock()
    mock_cloud_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)

    # Home info fails
    mock_cloud_wrapper.async_get_homes = AsyncMock(
        side_effect=HeimanApiError("Failed to get homes")
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Should not raise, but set error
    await coordinator._fetch_user_and_home_info()
    assert "home_info" in coordinator.data.errors


async def test_coordinator_fetch_devices_connection_error_no_previous_data(
    hass: HomeAssistant,
) -> None:
    """Test _fetch_and_process_devices with connection error and no previous data."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Simulate connection error
    mock_cloud_wrapper.async_get_devices = AsyncMock(
        side_effect=HeimanConnectionError("Connection failed")
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={})  # No previous devices

    # Should raise UpdateFailed
    with pytest.raises(UpdateFailed, match="Connection error fetching devices"):
        await coordinator._fetch_and_process_devices("test-home-id")


async def test_coordinator_fetch_devices_general_exception_no_previous_data(
    hass: HomeAssistant,
) -> None:
    """Test _fetch_and_process_devices with general exception and no previous data."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Simulate general exception
    mock_cloud_wrapper.async_get_devices = AsyncMock(
        side_effect=RuntimeError("Unexpected error")
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={})  # No previous devices

    # Should raise UpdateFailed
    with pytest.raises(UpdateFailed, match="Failed to fetch devices"):
        await coordinator._fetch_and_process_devices("test-home-id")


async def test_coordinator_update_device_details(hass: HomeAssistant) -> None:
    """Test _update_device_details calls SDK method."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    mock_cloud_wrapper.async_fetch_and_process_device_details = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"

    await coordinator._update_device_details({"device-1": mock_device})

    mock_cloud_wrapper.async_fetch_and_process_device_details.assert_called_once()


async def test_coordinator_merge_device_states(hass: HomeAssistant) -> None:
    """Test _merge_device_states merges old device states."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Create old device
    old_device = MagicMock(spec=HeimanDevice)
    old_device.device_id = "device-1"
    old_device.properties = {
        "temp": SDKDeviceProperty(
            identifier="temp",
            name="Temperature",
            value=20.0,
            readable=True,
        )
    }

    # Create new device
    new_device = MagicMock(spec=HeimanDevice)
    new_device.device_id = "device-1"
    new_device.properties = {
        "humidity": SDKDeviceProperty(
            identifier="humidity",
            name="Humidity",
            value=60.0,
            readable=True,
        )
    }
    new_device.merge_from = MagicMock()

    coordinator.data = HeimanData(devices={"device-1": old_device})

    # Merge states
    coordinator._merge_device_states({"device-1": new_device})

    # Verify merge_from was called
    new_device.merge_from.assert_called_once_with(old_device)
    assert coordinator.data.devices["device-1"] == new_device


async def test_coordinator_mqtt_init_oauth2_token_path(hass: HomeAssistant) -> None:
    """Test MQTT init gets token from OAuth2 session."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        CONF_USER_ID: "test-user",
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Mock OAuth2 session with valid token
    mock_session = MagicMock()
    mock_session.token = {"access_token": "oauth2-token"}
    mock_session.async_ensure_token_valid = AsyncMock()
    coordinator.oauth_session = mock_session

    # Mock MQTT client
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        await coordinator.async_init_mqtt_client()

        # Verify token was retrieved from OAuth2 session
        mock_mqtt_class.assert_called_once()
        call_kwargs = mock_mqtt_class.call_args
        assert call_kwargs[1]["access_token"] == "oauth2-token"


async def test_coordinator_mqtt_init_no_user_id(hass: HomeAssistant) -> None:
    """Test MQTT init returns early when user_id missing."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        "token": {"access_token": "test-token"},
        # No CONF_USER_ID
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Should return early without creating MQTT client
    await coordinator.async_init_mqtt_client()
    assert coordinator.mqtt_client is None


async def test_coordinator_mqtt_init_with_user_info(hass: HomeAssistant) -> None:
    """Test MQTT init gets user display name from user_info."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        CONF_USER_ID: "test-user",
        "token": {"access_token": "test-token"},
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Set user_info
    mock_user = MagicMock()
    mock_user.get_display_name = MagicMock(return_value="Test User")
    coordinator.data = HeimanData(user_info=mock_user)

    # Mock MQTT client
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        await coordinator.async_init_mqtt_client()

        # Verify user display name was used
        mock_mqtt_class.assert_called_once()
        call_kwargs = mock_mqtt_class.call_args
        assert call_kwargs[1]["user_display_name"] == "Test User"


async def test_coordinator_mqtt_init_cloud_client_access_error(
    hass: HomeAssistant,
) -> None:
    """Test MQTT init handles missing cloud_client gracefully."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        CONF_USER_ID: "test-user",
        "token": {"access_token": "test-token"},
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    # Configure cloud_client property to raise RuntimeError when accessed
    type(mock_api_client).cloud_client = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("Client not initialized"))
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Mock OAuth2 session
    mock_session = MagicMock()
    mock_session.token = {"access_token": "test-token"}
    mock_session.async_ensure_token_valid = AsyncMock()
    coordinator.oauth_session = mock_session

    # Mock MQTT client
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        # Should handle missing _wrapper gracefully
        await coordinator.async_init_mqtt_client()

        # MQTT client should still be created with cloud_client=None
        mock_mqtt_class.assert_called_once()
        call_kwargs = mock_mqtt_class.call_args
        assert call_kwargs[1]["cloud_client"] is None


async def test_coordinator_mqtt_init_heiman_mqtt_error(hass: HomeAssistant) -> None:
    """Test MQTT init re-raises HeimanMQTTError after cleanup."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        CONF_USER_ID: "test-user",
        "token": {"access_token": "test-token"},
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Mock OAuth2 session
    mock_session = MagicMock()
    mock_session.token = {"access_token": "test-token"}
    mock_session.async_ensure_token_valid = AsyncMock()
    coordinator.oauth_session = mock_session

    # Mock MQTT client that raises HeimanMQTTError during connect
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock(
            side_effect=HeimanMQTTError("MQTT connection failed")
        )
        # Add async_disconnect as the first available method
        mock_mqtt_instance.async_disconnect = AsyncMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        # Exception should be re-raised after cleanup
        with pytest.raises(HeimanMQTTError, match="MQTT connection failed"):
            await coordinator.async_init_mqtt_client()

        # MQTT client should be cleared after failure
        assert coordinator.mqtt_client is None
        # async_disconnect should have been called (first in the list)
        mock_mqtt_instance.async_disconnect.assert_called_once()


async def test_coordinator_on_device_property_update_new_property(
    hass: HomeAssistant,
) -> None:
    """Test _on_device_property_update adds new property."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.properties = {}

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={"device-1": mock_device})
    coordinator.hass = hass

    # Mock async_set_updated_data
    coordinator.async_set_updated_data = AsyncMock()

    # Call with new property
    coordinator._on_device_property_update("device-1", {"new_prop": 42})

    # Verify new property was added
    assert "new_prop" in mock_device.properties
    assert mock_device.properties["new_prop"].value == 42


async def test_coordinator_read_device_properties_no_properties_returned(
    hass: HomeAssistant,
) -> None:
    """Test async_read_device_properties when no properties returned."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.properties = {}
    mock_device.product_id = "test-product"

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={"device-1": mock_device})

    # Mock MQTT client that returns empty dict
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_read_properties = AsyncMock(return_value={})
    coordinator.mqtt_client = mock_mqtt_client

    # Read properties - should log warning
    await coordinator.async_read_device_properties("device-1")

    # Verify warning was logged (no properties returned)
    mock_mqtt_client.async_read_properties.assert_called_once()


async def test_coordinator_get_online_devices(hass: HomeAssistant) -> None:
    """Test get_online_devices filters online devices."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    online_device = MagicMock(spec=HeimanDevice)
    online_device.device_id = "device-1"
    online_device.online = True

    offline_device = MagicMock(spec=HeimanDevice)
    offline_device.device_id = "device-2"
    offline_device.online = False

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(
        devices={"device-1": online_device, "device-2": offline_device}
    )

    # Get online devices
    online_devices = coordinator.get_online_devices()

    assert len(online_devices) == 1
    assert online_devices[0].device_id == "device-1"


async def test_coordinator_get_device_property_not_found(hass: HomeAssistant) -> None:
    """Test get_device_property returns None when device or property not found."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={})

    # Test device not found
    result = coordinator.get_device_property("non-existent", "prop")
    assert result is None

    # Test property not found
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.properties = {}
    coordinator.data.devices["device-1"] = mock_device

    result = coordinator.get_device_property("device-1", "non-existent")
    assert result is None


async def test_coordinator_async_update_data_success(hass: HomeAssistant) -> None:
    """Test _async_update_data successful execution."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Mock user info
    mock_user = MagicMock()
    mock_cloud_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)

    # Mock homes
    mock_home = MagicMock()
    mock_home.home_id = "test-home-id"
    mock_cloud_wrapper.async_get_homes = AsyncMock(return_value=[mock_home])

    # Mock devices
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.merge_from = MagicMock()
    mock_cloud_wrapper.async_get_devices = AsyncMock(
        return_value={"device-1": mock_device}
    )
    mock_cloud_wrapper.async_fetch_and_process_device_details = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Execute update
    result = await coordinator._async_update_data()

    # Verify data was updated
    assert result.user_info is not None
    assert result.home_info is not None
    assert result.last_update is not None
    assert "device-1" in result.devices


async def test_coordinator_fetch_home_info_with_matching_home(
    hass: HomeAssistant,
) -> None:
    """Test _fetch_user_and_home_info finds matching home by ID."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "target-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Mock user info
    mock_user = MagicMock()
    mock_cloud_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)

    # Mock homes - return multiple homes, one matching
    mock_home1 = MagicMock()
    mock_home1.home_id = "other-home-id"
    mock_home2 = MagicMock()
    mock_home2.home_id = "target-home-id"
    mock_cloud_wrapper.async_get_homes = AsyncMock(
        return_value=[mock_home1, mock_home2]
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    await coordinator._fetch_user_and_home_info()

    # Should find the matching home
    assert coordinator.data.home_info.home_id == "target-home-id"


async def test_coordinator_fetch_home_info_home_not_found(
    hass: HomeAssistant,
) -> None:
    """Test _fetch_user_and_home_info raises UpdateFailed when home_id not found."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "non-existent-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Mock user info
    mock_user = MagicMock()
    mock_cloud_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)

    # Mock homes - return homes but none matching the configured home_id
    mock_home1 = MagicMock()
    mock_home1.home_id = "home-1"
    mock_home2 = MagicMock()
    mock_home2.home_id = "home-2"
    mock_cloud_wrapper.async_get_homes = AsyncMock(
        return_value=[mock_home1, mock_home2]
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Should raise UpdateFailed with clear error message
    with pytest.raises(UpdateFailed, match="non-existent-home-id.*was not found"):
        await coordinator._fetch_user_and_home_info()


async def test_coordinator_fetch_home_info_auth_error(
    hass: HomeAssistant,
) -> None:
    """Test _fetch_user_and_home_info raises ConfigEntryAuthFailed on HeimanAuthError."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Mock user info - already exists so we skip the first try block
    mock_user = MagicMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()
    coordinator.data.user_info = mock_user  # Set user_info to skip first try block

    # Mock async_get_homes to raise HeimanAuthError
    mock_cloud_wrapper.async_get_homes = AsyncMock(
        side_effect=HeimanAuthError("Token expired")
    )

    # Should raise ConfigEntryAuthFailed to trigger re-auth flow
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._fetch_user_and_home_info()


async def test_coordinator_fetch_home_info_config_entry_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Test _fetch_user_and_home_info re-raises ConfigEntryAuthFailed for home info."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Mock user info - already exists so we skip the first try block
    mock_user = MagicMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()
    coordinator.data.user_info = mock_user  # Set user_info to skip first try block

    # Mock async_get_homes to raise ConfigEntryAuthFailed directly
    mock_cloud_wrapper.async_get_homes = AsyncMock(
        side_effect=ConfigEntryAuthFailed("Already authenticated failed")
    )

    # Should re-raise ConfigEntryAuthFailed unchanged
    with pytest.raises(ConfigEntryAuthFailed, match="Already authenticated failed"):
        await coordinator._fetch_user_and_home_info()


async def test_coordinator_fetch_devices_with_filtering(hass: HomeAssistant) -> None:
    """Test _fetch_and_process_devices applies device filtering."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Create mock device management
    mock_device_management = MagicMock()
    mock_filter_manager = MagicMock()
    mock_device_management.filter_manager = mock_filter_manager

    # Create devices
    mock_device1 = MagicMock(spec=HeimanDevice)
    mock_device1.device_id = "device-1"
    mock_device1.merge_from = MagicMock()

    mock_device2 = MagicMock(spec=HeimanDevice)
    mock_device2.device_id = "device-2"
    mock_device2.merge_from = MagicMock()

    # Return only device-1 after filtering
    mock_filter_manager.get_filtered_devices = MagicMock(return_value=[mock_device1])

    mock_cloud_wrapper.async_get_devices = AsyncMock(
        return_value={"device-1": mock_device1, "device-2": mock_device2}
    )
    mock_cloud_wrapper.async_fetch_and_process_device_details = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
        device_management=mock_device_management,
    )

    coordinator.data = HeimanData()

    await coordinator._fetch_and_process_devices("test-home-id")

    # Verify filtering was applied
    mock_filter_manager.get_filtered_devices.assert_called_once()
    assert "device-1" in coordinator.data.devices
    assert "device-2" not in coordinator.data.devices


async def test_coordinator_mqtt_init_oauth2_token_none_debug_log(
    hass: HomeAssistant,
) -> None:
    """Test MQTT init logs debug when OAuth2 token is None."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        CONF_USER_ID: "test-user",
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Mock OAuth2 session with token=None after validation
    mock_session = MagicMock()
    mock_session.token = None
    mock_session.async_ensure_token_valid = AsyncMock()
    coordinator.oauth_session = mock_session

    # Initialize MQTT - should log debug and return
    await coordinator.async_init_mqtt_client()

    # MQTT client should not be created
    assert coordinator.mqtt_client is None


async def test_coordinator_mqtt_init_no_access_token_warning(
    hass: HomeAssistant,
) -> None:
    """Test MQTT init warns when no access_token available."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOME_ID: "test-home-id",
        CONF_USER_ID: "test-user",
    }
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # No token in config, no oauth_session
    coordinator.oauth_session = None

    # Initialize MQTT - should warn and return
    await coordinator.async_init_mqtt_client()

    # MQTT client should not be created
    assert coordinator.mqtt_client is None


async def test_coordinator_on_device_property_update_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Test _on_device_property_update returns early when device not found."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={})

    # Call with non-existent device - should return early
    coordinator._on_device_property_update("non-existent", {"prop": 42})

    # No exception should be raised


async def test_coordinator_on_device_property_update_existing_property(
    hass: HomeAssistant,
) -> None:
    """Test _on_device_property_update updates existing property."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.properties = {
        "temperature": SDKDeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=20.0,
            readable=True,
        )
    }

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={"device-1": mock_device})
    coordinator.hass = hass
    coordinator.async_set_updated_data = AsyncMock()

    # Update existing property
    coordinator._on_device_property_update("device-1", {"temperature": 25.5})

    # Verify property was updated
    assert mock_device.properties["temperature"].value == 25.5


async def test_coordinator_read_device_properties_mqtt_not_initialized(
    hass: HomeAssistant,
) -> None:
    """Test async_read_device_properties warns when MQTT not initialized."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()
    coordinator.mqtt_client = None

    # Should warn and return early
    await coordinator.async_read_device_properties("device-1")


async def test_coordinator_read_device_properties_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Test async_read_device_properties warns when device not found."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={})

    mock_mqtt_client = MagicMock()
    coordinator.mqtt_client = mock_mqtt_client

    # Should warn and return early
    await coordinator.async_read_device_properties("non-existent")


async def test_coordinator_read_device_properties_exception(
    hass: HomeAssistant,
) -> None:
    """Test async_read_device_properties handles exception."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.properties = {}
    mock_device.product_id = "test-product"

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={"device-1": mock_device})

    # Mock MQTT client that raises exception
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_read_properties = AsyncMock(
        side_effect=RuntimeError("Read failed")
    )
    coordinator.mqtt_client = mock_mqtt_client

    # Should handle exception gracefully
    await coordinator.async_read_device_properties("device-1")

    # Error should be logged but no exception raised


async def test_coordinator_get_device_property_success(hass: HomeAssistant) -> None:
    """Test get_device_property returns property value."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    # Create device with property
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.properties = {
        "temperature": SDKDeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            readable=True,
        )
    }
    coordinator.data.devices["device-1"] = mock_device

    # Get property value
    result = coordinator.get_device_property("device-1", "temperature")
    assert result == 25.5


async def test_coordinator_fetch_user_info_auth_failed(hass: HomeAssistant) -> None:
    """Test _fetch_user_and_home_info re-raises ConfigEntryAuthFailed for user info."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Simulate authentication failure
    mock_cloud_wrapper.async_get_user_info = AsyncMock(
        side_effect=ConfigEntryAuthFailed("Token expired")
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData()

    # Should re-raise ConfigEntryAuthFailed without wrapping it
    with pytest.raises(ConfigEntryAuthFailed, match="Token expired"):
        await coordinator._fetch_user_and_home_info()


async def test_coordinator_fetch_devices_auth_failed(hass: HomeAssistant) -> None:
    """Test _fetch_and_process_devices re-raises ConfigEntryAuthFailed."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Simulate authentication failure
    mock_cloud_wrapper.async_get_devices = AsyncMock(
        side_effect=ConfigEntryAuthFailed("Token expired")
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={})

    # Should re-raise ConfigEntryAuthFailed without wrapping it
    with pytest.raises(ConfigEntryAuthFailed, match="Token expired"):
        await coordinator._fetch_and_process_devices("test-home-id")


async def test_coordinator_fetch_devices_heiman_auth_error(
    hass: HomeAssistant,
) -> None:
    """Test _fetch_and_process_devices raises ConfigEntryAuthFailed on HeimanAuthError."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {CONF_HOME_ID: "test-home-id"}
    config_entry.entry_id = "test-entry"

    mock_api_client = MagicMock()
    mock_cloud_wrapper = MagicMock(spec=HeimanCloudClientWrapper)
    mock_api_client.cloud_client = mock_cloud_wrapper
    mock_api_client.initialize = AsyncMock()

    # Simulate HeimanAuthError from SDK
    mock_cloud_wrapper.async_get_devices = AsyncMock(
        side_effect=HeimanAuthError("Token expired")
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=config_entry,
    )

    coordinator.data = HeimanData(devices={})

    # Should raise ConfigEntryAuthFailed to trigger re-auth flow
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._fetch_and_process_devices("test-home-id")
