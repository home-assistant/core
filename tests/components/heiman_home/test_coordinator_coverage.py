"""Additional tests for Heiman Home coordinator to improve coverage."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import HeimanConnectionError, HeimanMQTTError
from heimanconnect.models import DeviceProperty, HeimanDevice
import pytest

from homeassistant.components.heiman_home.const import (
    CONF_HOME_ID,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.components.heiman_home.coordinator import (
    HeimanDataUpdateCoordinator,
    _infer_entity_type,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


# Test _infer_entity_type function
def test_infer_entity_type_none_value() -> None:
    """Test _infer_entity_type with None value."""
    # None is a scalar-like value, so it returns 'sensor'
    assert _infer_entity_type(None) == "sensor"


def test_infer_entity_type_bool() -> None:
    """Test _infer_entity_type with boolean value."""
    # Boolean values return None because sensor platform rejects bool native values
    assert _infer_entity_type(True) is None
    assert _infer_entity_type(False) is None


def test_infer_entity_type_int() -> None:
    """Test _infer_entity_type with integer value."""
    assert _infer_entity_type(42) == "sensor"
    assert _infer_entity_type(-10) == "sensor"


def test_infer_entity_type_float() -> None:
    """Test _infer_entity_type with float value."""
    assert _infer_entity_type(25.5) == "sensor"
    assert _infer_entity_type(-3.14) == "sensor"


def test_infer_entity_type_string() -> None:
    """Test _infer_entity_type with string value."""
    assert _infer_entity_type("test") == "sensor"
    assert _infer_entity_type("") == "sensor"


def test_infer_entity_type_dict() -> None:
    """Test _infer_entity_type with dict value."""
    assert _infer_entity_type({"key": "value"}) is None


def test_infer_entity_type_list() -> None:
    """Test _infer_entity_type with list value."""
    assert _infer_entity_type([1, 2, 3]) is None


def test_infer_entity_type_tuple() -> None:
    """Test _infer_entity_type with tuple value."""
    assert _infer_entity_type((1, 2)) is None


def test_infer_entity_type_set() -> None:
    """Test _infer_entity_type with set value."""
    assert _infer_entity_type({1, 2, 3}) is None


async def test_coordinator_update_user_info_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test coordinator update with user info connection error."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(
        side_effect=HeimanConnectionError("Connection failed")
    )
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    with pytest.raises(UpdateFailed, match="Connection error"):
        await coordinator._async_update_data()


async def test_coordinator_update_user_info_generic_exception(
    hass: HomeAssistant,
) -> None:
    """Test coordinator update with user info generic exception."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(side_effect=Exception("Generic error"))
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    with pytest.raises(UpdateFailed, match="Failed to fetch user info"):
        await coordinator._async_update_data()


async def test_coordinator_device_fetch_connection_error_no_history(
    hass: HomeAssistant,
) -> None:
    """Test device fetch with connection error and no history."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])
    mock_wrapper.async_get_devices = AsyncMock(
        side_effect=HeimanConnectionError("Connection failed")
    )
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First update - should raise because no history
    with pytest.raises(UpdateFailed, match="Connection error fetching devices"):
        await coordinator._async_update_data()


async def test_coordinator_device_fetch_generic_exception_no_history(
    hass: HomeAssistant,
) -> None:
    """Test device fetch with generic exception and no history."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])
    mock_wrapper.async_get_devices = AsyncMock(side_effect=Exception("Generic error"))
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # First update - should raise because no history
    with pytest.raises(UpdateFailed, match="Failed to fetch devices"):
        await coordinator._async_update_data()


async def test_coordinator_merge_preserves_old_properties(
    hass: HomeAssistant,
) -> None:
    """Test that merge preserves old properties when new values are None."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])

    # Create old device with property value
    old_device = MagicMock(spec=HeimanDevice)
    old_device.device_id = "device-1"
    old_device.online = True
    old_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.0,
            readable=True,
            entity="sensor",
        )
    }

    # Create new device with None value
    new_device = MagicMock(spec=HeimanDevice)
    new_device.device_id = "device-1"
    new_device.online = None
    new_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=None,
            readable=True,
            entity="sensor",
        )
    }

    mock_wrapper.async_get_devices = AsyncMock(return_value={"device-1": new_device})
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Set old device in coordinator data
    coordinator.data.devices = {"device-1": old_device}

    # Perform merge
    coordinator._merge_device_states({"device-1": new_device})

    # Old value should be preserved
    assert new_device.properties["temperature"].value == 25.0
    # Online status should be preserved
    assert new_device.online is True


async def test_coordinator_mqtt_init_no_access_token(
    hass: HomeAssistant,
) -> None:
    """Test MQTT initialization without access token."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {},  # No access_token
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_init_mqtt_client()

    # MQTT client should not be initialized
    assert coordinator.mqtt_client is None


async def test_coordinator_mqtt_init_no_user_id(
    hass: HomeAssistant,
) -> None:
    """Test MQTT initialization without user ID."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            # No CONF_USER_ID
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    await coordinator.async_init_mqtt_client()

    # MQTT client should not be initialized
    assert coordinator.mqtt_client is None


async def test_coordinator_mqtt_init_with_oauth_session(
    hass: HomeAssistant,
) -> None:
    """Test MQTT initialization using OAuth session."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    mock_oauth_session = MagicMock()
    mock_oauth_session.async_ensure_token_valid = AsyncMock()
    mock_oauth_session.token = {"access_token": "session-token"}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {},  # No token in config
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
        oauth_session=mock_oauth_session,
    )

    coordinator.data.user_info = MagicMock()
    coordinator.data.user_info.nick_name = None
    coordinator.data.user_info.email = "test@example.com"

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_instance = MagicMock()
        mock_mqtt_instance.connect = AsyncMock()
        mock_mqtt_instance.register_device_callback = MagicMock()
        mock_mqtt_class.return_value = mock_mqtt_instance

        await coordinator.async_init_mqtt_client()

        # MQTT client should be initialized with session token
        assert coordinator.mqtt_client is not None
        mock_mqtt_class.assert_called_once()
        call_kwargs = mock_mqtt_class.call_args[1]
        assert call_kwargs["access_token"] == "session-token"


async def test_coordinator_mqtt_init_exception(
    hass: HomeAssistant,
) -> None:
    """Test MQTT initialization with exception."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    coordinator.data.user_info = MagicMock()
    coordinator.data.user_info.nick_name = "Test User"

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient"
    ) as mock_mqtt_class:
        mock_mqtt_class.side_effect = HeimanMQTTError("MQTT error")

        await coordinator.async_init_mqtt_client()

        # MQTT client should not be initialized due to exception
        assert coordinator.mqtt_client is None


async def test_coordinator_on_device_property_update_new_property(
    hass: HomeAssistant,
) -> None:
    """Test MQTT property update adds new property."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Create device without the property
    device = MagicMock(spec=HeimanDevice)
    device.device_id = "device-1"
    device.properties = {}
    coordinator.data.devices = {"device-1": device}

    # Simulate MQTT update with new property
    coordinator._on_device_property_update("device-1", {"new_prop": 42})

    # New property should be added
    assert "new_prop" in device.properties
    assert device.properties["new_prop"].value == 42
    assert device.properties["new_prop"].entity == "sensor"


async def test_coordinator_on_device_property_update_existing_property(
    hass: HomeAssistant,
) -> None:
    """Test MQTT property update updates existing property."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Create device with existing property
    device = MagicMock(spec=HeimanDevice)
    device.device_id = "device-1"
    device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=20.0,
            readable=True,
            entity="sensor",
        )
    }
    coordinator.data.devices = {"device-1": device}

    # Simulate MQTT update with updated value
    coordinator._on_device_property_update("device-1", {"temperature": 25.5})

    # Property value should be updated
    assert device.properties["temperature"].value == 25.5


async def test_coordinator_on_device_property_update_unknown_device(
    hass: HomeAssistant,
) -> None:
    """Test MQTT property update for unknown device."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    coordinator.data.devices = {}

    # Should not raise for unknown device
    coordinator._on_device_property_update("unknown-device", {"temp": 25})


async def test_coordinator_read_device_properties_no_mqtt(
    hass: HomeAssistant,
) -> None:
    """Test read device properties without MQTT client."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Should return early without error
    await coordinator.async_read_device_properties("device-1")


async def test_coordinator_read_device_properties_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Test read device properties for non-existent device."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    mock_mqtt = MagicMock()
    mock_mqtt.async_read_properties = AsyncMock(return_value={})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )
    coordinator.mqtt_client = mock_mqtt
    coordinator.data.devices = {}

    # Should return early without error
    await coordinator.async_read_device_properties("device-1")


async def test_coordinator_read_device_properties_exception(
    hass: HomeAssistant,
) -> None:
    """Test read device properties with exception."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    mock_mqtt = MagicMock()
    mock_mqtt.async_read_properties = AsyncMock(side_effect=Exception("Read failed"))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )
    coordinator.mqtt_client = mock_mqtt

    device = MagicMock(spec=HeimanDevice)
    device.device_id = "device-1"
    device.product_id = "product-1"
    device.properties = {}
    coordinator.data.devices = {"device-1": device}

    # Should handle exception gracefully
    await coordinator.async_read_device_properties("device-1")


async def test_coordinator_get_device_property_not_found(
    hass: HomeAssistant,
) -> None:
    """Test get device property when device or property not found."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    coordinator.data.devices = {}

    # Should return None for non-existent device
    assert coordinator.get_device_property("device-1", "temp") is None


async def test_coordinator_convert_dbm_to_level() -> None:
    """Test DBM to level conversion."""
    mock_api_client = MagicMock()
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )

    coordinator = HeimanDataUpdateCoordinator(
        hass=MagicMock(),
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    assert coordinator._convert_dbm_to_level(-40) == "strong"
    assert coordinator._convert_dbm_to_level(-50) == "strong"
    assert coordinator._convert_dbm_to_level(-60) == "medium"
    assert coordinator._convert_dbm_to_level(-65) == "medium"
    assert coordinator._convert_dbm_to_level(-70) == "weak"
    assert coordinator._convert_dbm_to_level(-75) == "weak"
    assert coordinator._convert_dbm_to_level(-80) == "very_weak"
    assert coordinator._convert_dbm_to_level(-100) == "very_weak"


async def test_coordinator_device_detail_cache_hit(hass: HomeAssistant) -> None:
    """Test device detail fetching with cache hit."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])
    mock_wrapper.async_get_devices = AsyncMock(return_value={})
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Pre-populate cache
    coordinator._device_detail_cache["device-1"] = {
        "firmwareInfo": {"version": "1.0.0"}
    }
    coordinator._device_detail_cache_timestamp = datetime.now(UTC)

    # Create a mock device
    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.firmware_version = None
    mock_device.properties = {}

    devices = {"device-1": mock_device}

    # Should use cache and not call API
    await coordinator._update_device_details(devices)

    # Verify _async_get_device_detail was not called (cache hit)
    mock_wrapper._async_get_device_detail.assert_not_called()


async def test_coordinator_extract_firmware_versions(hass: HomeAssistant) -> None:
    """Test firmware version extraction from raw_data and firmware_info."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])
    mock_wrapper.async_get_devices = AsyncMock(return_value={})
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Test case 1: Extract from raw_data
    device1 = MagicMock()
    device1.raw_data = {"firmwareInfo": {"version": "2.0.0"}}
    device1.firmware_info = None
    device1.firmware_version = None

    # Test case 2: Extract from firmware_info
    device2 = MagicMock()
    device2.raw_data = None
    device2.firmware_info = {"version": "3.0.0"}
    device2.firmware_version = None

    devices = {"device-1": device1, "device-2": device2}

    coordinator._extract_firmware_versions(devices)

    assert device1.firmware_version == "2.0.0"
    assert device2.firmware_version == "3.0.0"


async def test_coordinator_process_device_info(hass: HomeAssistant) -> None:
    """Test _process_device_info method."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])
    mock_wrapper.async_get_devices = AsyncMock(return_value={})
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Create a mock device with properties
    device = MagicMock()
    device.properties = {
        "DeviceINFO_MAC": DeviceProperty(
            identifier="DeviceINFO_MAC", name="MAC", value=None
        ),
        "DeviceINFO_DBM": DeviceProperty(
            identifier="DeviceINFO_DBM", name="DBM", value=None
        ),
        "DeviceINFO_IP": DeviceProperty(
            identifier="DeviceINFO_IP", name="IP", value=None
        ),
    }

    device_info = {
        "MAC": "AA:BB:CC:DD:EE:FF",
        "DBM": -65,
        "IP": "192.168.1.100",
    }

    coordinator._process_device_info(device, device_info)

    assert device.properties["DeviceINFO_MAC"].value == "AA:BB:CC:DD:EE:FF"
    assert device.properties["DeviceINFO_DBM"].value == -65
    assert device.properties["DeviceINFO_IP"].value == "192.168.1.100"
    # DBM_Level should be created automatically
    assert "DeviceINFO_DBM_Level" in device.properties
    assert device.properties["DeviceINFO_DBM_Level"].value == "medium"


async def test_coordinator_update_missing_home_id(hass: HomeAssistant) -> None:
    """Test coordinator update with missing home ID."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            # Missing CONF_HOME_ID
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    with pytest.raises(UpdateFailed, match="Home ID not found"):
        await coordinator._async_update_data()


async def test_coordinator_fetch_home_info_exception(hass: HomeAssistant) -> None:
    """Test fetching home info with exception."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(side_effect=Exception("Home fetch failed"))
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Should not raise, but store error
    await coordinator._fetch_user_and_home_info()
    assert "home_info" in coordinator.data.errors


async def test_coordinator_device_filtering(hass: HomeAssistant) -> None:
    """Test device filtering logic."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])

    # Create mock devices using MagicMock instead of HeimanDevice
    device1 = MagicMock()
    device1.device_id = "device-1"
    device2 = MagicMock()
    device2.device_id = "device-2"

    mock_wrapper.async_get_devices = AsyncMock(
        return_value={"device-1": device1, "device-2": device2}
    )
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    # Create mock device management
    mock_device_management = MagicMock()
    mock_filter_manager = MagicMock()
    mock_filter_manager.get_filtered_devices = MagicMock(return_value=[device1])
    mock_device_management.filter_manager = mock_filter_manager

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
        device_management=mock_device_management,
    )

    # This should apply filtering
    await coordinator._fetch_and_process_devices("home-1")
    mock_filter_manager.get_filtered_devices.assert_called_once()


async def test_coordinator_cache_expiry(hass: HomeAssistant) -> None:
    """Test device detail cache expiry."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])
    mock_wrapper.async_get_devices = AsyncMock(return_value={})
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Set cache timestamp to past (expired)
    coordinator._device_detail_cache["device-1"] = {"data": "old"}
    coordinator._device_detail_cache_timestamp = datetime.now(UTC) - timedelta(
        seconds=600
    )  # 10 minutes ago

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.firmware_version = None
    mock_device.properties = {}

    devices = {"device-1": mock_device}

    # Cache should be cleared due to expiry
    await coordinator._update_device_details(devices)

    # Old cache should be cleared
    assert (
        "device-1" not in coordinator._device_detail_cache
        or coordinator._device_detail_cache.get("device-1") is None
    )


async def test_coordinator_derive_metadata_parsing(hass: HomeAssistant) -> None:
    """Test deriveMetadata parsing and property updates."""
    import json

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])
    mock_wrapper.async_get_devices = AsyncMock(return_value={})
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Create a device with properties
    device = MagicMock()
    device.device_id = "device-1"
    device.firmware_version = None
    device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=None
        ),
        "humidity": DeviceProperty(identifier="humidity", name="Humidity", value=None),
    }

    # Create deriveMetadata
    metadata_list = [
        {"property": "temperature", "value": 25.5},
        {"property": "humidity", "value": 60},
    ]
    device_detail = {
        "firmwareInfo": {"version": "1.0.0"},
        "deriveMetadata": json.dumps(metadata_list),
    }

    coordinator._process_device_detail(device, device_detail)

    assert device.firmware_version == "1.0.0"
    assert device.properties["temperature"].value == 25.5
    assert device.properties["humidity"].value == 60


async def test_coordinator_rssi_property_update(hass: HomeAssistant) -> None:
    """Test RSSI property special handling."""
    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=MagicMock())
    mock_wrapper.async_get_homes = AsyncMock(return_value=[MagicMock()])
    mock_wrapper.async_get_devices = AsyncMock(return_value={})
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client._ensure_initialized = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home-1",
            CONF_USER_ID: "user-1",
        },
        unique_id="user-1",
    )
    entry.add_to_hass(hass)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_client=mock_api_client,
        config_entry=entry,
    )

    # Create a device with RSSI, DBM and DBM_Level properties
    device = MagicMock()
    device.device_id = "device-1"
    device.firmware_version = None
    device.properties = {
        "RSSI": DeviceProperty(identifier="RSSI", name="RSSI", value=None),
        "DeviceINFO_DBM": DeviceProperty(
            identifier="DeviceINFO_DBM", name="DBM", value=None
        ),
        "DeviceINFO_DBM_Level": DeviceProperty(
            identifier="DeviceINFO_DBM_Level", name="DBM Level", value=None
        ),
    }

    # Update with numeric RSSI value
    prop_item = {"property": "RSSI", "value": -65}
    coordinator._update_device_property(device, prop_item)

    # RSSI should keep numeric value
    assert device.properties["RSSI"].value == -65
    # DBM_Level should be created
    assert "DeviceINFO_DBM_Level" in device.properties
    assert device.properties["DeviceINFO_DBM_Level"].value == "medium"
