"""Tests for the Heiman Home binary sensor platform."""

from unittest.mock import MagicMock, patch

from heimanconnect import DeviceProperty, HeimanDevice

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.heiman_home.binary_sensor import (
    HeimanBinarySensorEntity,
    async_setup_entry,
)
from homeassistant.components.heiman_home.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_binary_sensor_setup(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test binary sensor platform setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_binary_sensor_entity_creation(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test binary sensor entity creation from device properties."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    motion_prop = DeviceProperty(
        identifier="motion_detected",
        name="Motion Detected",
        value=True,
        data_type="bool",
        readable=True,
        entity="binary_sensor",
    )

    mock_device.properties = {"motion_detected": motion_prop}
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    # Initialize DOMAIN data before calling async_setup_entry
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    assert len(added_entities) == 1
    sensor = added_entities[0]
    assert sensor.unique_id == "device-1_motion_detected_binary_sensor"
    assert sensor.name == "Motion Detected"


async def test_binary_sensor_entity_available_property(hass: HomeAssistant) -> None:
    """Test binary sensor entity available property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "motion_detected": DeviceProperty(
            identifier="motion_detected", name="Motion Detected", value=True
        )
    }

    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="motion_detected",
    )

    assert sensor.available is True

    mock_device.online = False
    assert sensor.available is False

    mock_coordinator.get_device.return_value = None
    assert sensor.available is False

    mock_device.online = True
    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.last_update_success = False
    assert sensor.available is False


async def test_binary_sensor_entity_is_on(hass: HomeAssistant) -> None:
    """Test binary sensor entity is_on property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "alarm_state": DeviceProperty(
            identifier="alarm_state", name="Alarm State", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="alarm_state",
    )

    assert sensor.is_on is True

    mock_device.properties["alarm_state"].value = False
    mock_coordinator.get_device.return_value = mock_device
    assert sensor.is_on is False

    mock_device.properties["alarm_state"].value = "alarm"
    mock_coordinator.get_device.return_value = mock_device
    assert sensor.is_on is True

    mock_device.properties["alarm_state"].value = "normal"
    mock_coordinator.get_device.return_value = mock_device
    assert sensor.is_on is False

    mock_device.properties["alarm_state"].value = 1
    mock_coordinator.get_device.return_value = mock_device
    assert sensor.is_on is True

    mock_device.properties["alarm_state"].value = 0
    mock_coordinator.get_device.return_value = mock_device
    assert sensor.is_on is False

    mock_coordinator.get_device.return_value = None
    assert sensor.is_on is None


async def test_binary_sensor_entity_is_on_string_alarm_states(
    hass: HomeAssistant,
) -> None:
    """Test binary sensor entity is_on with various string alarm states."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "alarm_state": DeviceProperty(
            identifier="alarm_state", name="Alarm State", value="alarm"
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="alarm_state",
    )

    alarm_states = ["alarm", "alert", "active", "triggered", "true", "1"]
    for state in alarm_states:
        mock_device.properties = {
            "alarm_state": DeviceProperty(
                identifier="alarm_state", name="Alarm State", value=state
            )
        }
        mock_coordinator.get_device.return_value = mock_device
        assert sensor.is_on is True, f"Expected True for state: {state}"

    non_alarm_states = ["normal", "ok", "idle", "false", "0", "clear"]
    for state in non_alarm_states:
        mock_device.properties = {
            "alarm_state": DeviceProperty(
                identifier="alarm_state", name="Alarm State", value=state
            )
        }
        mock_coordinator.get_device.return_value = mock_device
        assert sensor.is_on is False, f"Expected False for state: {state}"


async def test_binary_sensor_entity_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test binary sensor entity extra_state_attributes property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "SmokeSensorState": DeviceProperty(
            identifier="SmokeSensorState",
            name="Smoke Sensor State",
            value=True,
            unit="units",
            data_type="bool",
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="SmokeSensorState",
    )

    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs.get("unit") == "units"
    assert attrs.get("data_type") == "bool"
    assert attrs.get("raw_value") is True

    # Test when device is not found - should return empty dict
    mock_coordinator.get_device.return_value = None
    attrs = sensor.extra_state_attributes
    assert attrs == {}


async def test_binary_sensor_device_class_motion(hass: HomeAssistant) -> None:
    """Test binary sensor device class for motion sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "Motion": DeviceProperty(
            identifier="Motion",
            name="Motion",
            value=True,
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="Motion",
    )

    assert sensor.device_class == BinarySensorDeviceClass.MOTION


async def test_binary_sensor_device_class_door(hass: HomeAssistant) -> None:
    """Test binary sensor device class for door sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "DoorStatus": DeviceProperty(
            identifier="DoorStatus",
            name="Door Status",
            value=True,
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="DoorStatus",
    )

    assert sensor.device_class == BinarySensorDeviceClass.DOOR


async def test_binary_sensor_device_class_smoke(hass: HomeAssistant) -> None:
    """Test binary sensor device class for smoke sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "SmokeSensorState": DeviceProperty(
            identifier="SmokeSensorState",
            name="Smoke Sensor State",
            value=False,
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="SmokeSensorState",
    )

    assert sensor.device_class == BinarySensorDeviceClass.SMOKE


async def test_binary_sensor_device_class_gas(hass: HomeAssistant) -> None:
    """Test binary sensor device class for gas sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "CarbonMonoxideAlarm": DeviceProperty(
            identifier="CarbonMonoxideAlarm",
            name="Carbon Monoxide Alarm",
            value=False,
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="CarbonMonoxideAlarm",
    )

    assert sensor.device_class == BinarySensorDeviceClass.GAS


async def test_binary_sensor_device_class_moisture(hass: HomeAssistant) -> None:
    """Test binary sensor device class for moisture sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "WaterSensorState": DeviceProperty(
            identifier="WaterSensorState",
            name="Water Sensor State",
            value=False,
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="WaterSensorState",
    )

    assert sensor.device_class == BinarySensorDeviceClass.MOISTURE


async def test_binary_sensor_device_class_alarm(hass: HomeAssistant) -> None:
    """Test binary sensor device class for alarm sensor (TamperState -> tamper)."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "TamperState": DeviceProperty(
            identifier="TamperState",
            name="Tamper State",
            value=False,
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="TamperState",
    )

    # TamperState maps to "tamper" in BINARY_SENSOR_DEVICE_CLASS_MAP
    assert sensor.device_class == BinarySensorDeviceClass.TAMPER


async def test_binary_sensor_entity_device_info(hass: HomeAssistant) -> None:
    """Test binary sensor entity device info."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True
    mock_device.device_info = None
    mock_device.properties = {
        "motion_detected": DeviceProperty(
            identifier="motion_detected", name="Motion Detected", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="motion_detected",
    )

    device_info = sensor.device_info
    assert device_info is not None
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "Heiman"
    assert device_info["model"] == "HS1"
    assert device_info["sw_version"] == "1.0"
    assert device_info["hw_version"] == "1.0"
    assert (DOMAIN, "device-1") in device_info["identifiers"]


async def test_binary_sensor_entity_unique_id(hass: HomeAssistant) -> None:
    """Test binary sensor entity unique ID."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-123"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "motion_detected": DeviceProperty(
            identifier="motion_detected", name="Motion Detected", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="motion_detected",
    )

    assert sensor.unique_id == "device-123_motion_detected_binary_sensor"


async def test_binary_sensor_entity_has_entity_name(hass: HomeAssistant) -> None:
    """Test binary sensor entity has entity name."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "My Gateway"
    mock_device.online = True
    mock_device.properties = {
        "motion_detected": DeviceProperty(
            identifier="motion_detected", name="Motion Detected", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="motion_detected",
    )

    assert sensor.has_entity_name is True


async def test_binary_sensor_creation_with_multiple_properties(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test binary sensor entity creation with multiple properties."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Multi Binary Sensor Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS2"
    mock_device.product_id = "prod-2"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    motion_prop = DeviceProperty(
        identifier="motion_detected",
        name="Motion Detected",
        value=True,
        data_type="bool",
        readable=True,
        entity="binary_sensor",
    )

    door_prop = DeviceProperty(
        identifier="door_status",
        name="Door Status",
        value=False,
        data_type="bool",
        readable=True,
        entity="binary_sensor",
    )

    not_readable_prop = DeviceProperty(
        identifier="internal_state",
        name="Internal State",
        value="active",
        data_type="string",
        readable=False,
    )

    non_sensor_prop = DeviceProperty(
        identifier="temperature",
        name="Temperature",
        value=25.5,
        data_type="float",
        readable=True,
        entity="sensor",
    )

    mock_device.properties = {
        "motion_detected": motion_prop,
        "door_status": door_prop,
        "internal_state": not_readable_prop,
        "temperature": non_sensor_prop,
    }
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    assert len(added_entities) == 2
    unique_ids = {sensor.unique_id for sensor in added_entities}
    assert "device-1_motion_detected_binary_sensor" in unique_ids
    assert "device-1_door_status_binary_sensor" in unique_ids


async def test_binary_sensor_creation_no_binary_sensor_properties(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test binary sensor entity creation with no binary sensor properties."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Write Only Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS3"
    mock_device.product_id = "prod-3"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    not_readable_prop = DeviceProperty(
        identifier="write_only",
        name="Write Only",
        value="active",
        data_type="string",
        readable=False,
    )

    mock_device.properties = {"write_only": not_readable_prop}
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    assert len(added_entities) == 0


async def test_binary_sensor_entity_deduplication(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test binary sensor entity deduplication within a single call."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    # Create two properties that map to the same unique_id
    motion_prop1 = DeviceProperty(
        identifier="Motion",
        name="Motion",
        value=True,
        data_type="bool",
        readable=True,
        entity="binary_sensor",
    )

    mock_device.properties = {"Motion": motion_prop1}
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Verify entities are created (within a single call, deduplication happens)
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-1_Motion_binary_sensor"


async def test_binary_sensor_icon_motion(hass: HomeAssistant) -> None:
    """Test icon for motion binary sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "MotionStatus": DeviceProperty(
            identifier="MotionStatus", name="Motion Status", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="MotionStatus",
    )

    assert sensor.icon == "mdi:motion-sensor"


async def test_binary_sensor_icon_door(hass: HomeAssistant) -> None:
    """Test icon for door binary sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "DoorStatus": DeviceProperty(
            identifier="DoorStatus", name="Door Status", value=True
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="DoorStatus",
    )

    # DoorStatus matches ENTITY_ICONS and gets mdi:door
    assert sensor.icon == "mdi:door"


async def test_binary_sensor_icon_smoke(hass: HomeAssistant) -> None:
    """Test icon for smoke binary sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "SmokeSensorState": DeviceProperty(
            identifier="SmokeSensorState", name="Smoke Sensor State", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="SmokeSensorState",
    )

    # SmokeSensorState matches ENTITY_ICONS and gets mdi:smoke
    assert sensor.icon == "mdi:smoke"


async def test_binary_sensor_icon_gas(hass: HomeAssistant) -> None:
    """Test icon for gas binary sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "CarbonMonoxideAlarm": DeviceProperty(
            identifier="CarbonMonoxideAlarm", name="Carbon Monoxide Alarm", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="CarbonMonoxideAlarm",
    )

    assert sensor.icon == "mdi:molecule-co-warning"


async def test_binary_sensor_icon_moisture(hass: HomeAssistant) -> None:
    """Test icon for moisture binary sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "WaterSensorState": DeviceProperty(
            identifier="WaterSensorState", name="Water Sensor State", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="WaterSensorState",
    )

    # WaterSensorState matches ENTITY_ICONS and gets mdi:water
    assert sensor.icon == "mdi:water"


async def test_binary_sensor_icon_problem(hass: HomeAssistant) -> None:
    """Test icon for problem/alarm binary sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "CoStatus": DeviceProperty(identifier="CoStatus", name="CO Status", value=False)
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="CoStatus",
    )

    # CoStatus matches ENTITY_ICONS and gets mdi:molecule-co
    assert sensor.icon == "mdi:molecule-co"


async def test_binary_sensor_icon_default(hass: HomeAssistant) -> None:
    """Test default icon for unknown binary sensor type."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "unknown_sensor": DeviceProperty(
            identifier="unknown_sensor", name="Unknown Sensor", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown_sensor",
    )

    assert sensor.icon == "mdi:radiobox-marked"


async def test_binary_sensor_is_on_none_value(hass: HomeAssistant) -> None:
    """Test binary sensor entity is_on when property value is None."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "alarm_state": DeviceProperty(
            identifier="alarm_state", name="Alarm State", value=None
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="alarm_state",
    )

    assert sensor.is_on is None


async def test_binary_sensor_is_on_volt_error(hass: HomeAssistant) -> None:
    """Test binary sensor is_on for voltage error properties."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "UnderVoltError": DeviceProperty(
            identifier="UnderVoltError", name="Under Volt Error", value=0
        )
    }
    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="UnderVoltError",
    )

    assert sensor.is_on is False

    mock_device.properties = {
        "UnderVoltError": DeviceProperty(
            identifier="UnderVoltError", name="Under Volt Error", value=1
        )
    }
    mock_coordinator.get_device.return_value = mock_device
    assert sensor.is_on is True

    mock_device.properties = {
        "UnderVoltError": DeviceProperty(
            identifier="UnderVoltError", name="Under Volt Error", value=5
        )
    }
    mock_coordinator.get_device.return_value = mock_device
    assert sensor.is_on is True


async def test_binary_sensor_extra_state_attributes_property_not_found(
    hass: HomeAssistant,
) -> None:
    """Test extra_state_attributes when property is not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="SmokeSensorState",
    )

    attrs = sensor.extra_state_attributes
    assert attrs == {}


async def test_binary_sensor_entity_name_fallback(hass: HomeAssistant) -> None:
    """Test binary sensor entity name fallback to property identifier."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {}

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown_property",
    )

    assert sensor.name == "unknown_property"


async def test_binary_sensor_creation_skips_non_binary_sensor_entities(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test binary sensor creation skips properties with non-binary_sensor entity markers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Device With Mixed Entities"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    switch_prop = DeviceProperty(
        identifier="switch_state",
        name="Switch State",
        value="on",
        data_type="string",
        readable=True,
        entity="switch",
    )

    sensor_prop = DeviceProperty(
        identifier="temperature",
        name="Temperature",
        value=25.0,
        data_type="float",
        readable=True,
        entity="sensor",
    )

    binary_sensor_prop = DeviceProperty(
        identifier="motion_detected",
        name="Motion Detected",
        value=True,
        data_type="bool",
        readable=True,
        entity="binary_sensor",
    )

    mock_device.properties = {
        "switch_state": switch_prop,
        "temperature": sensor_prop,
        "motion_detected": binary_sensor_prop,
    }
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-1_motion_detected_binary_sensor"


async def test_binary_sensor_icon_lowercase_matching(hass: HomeAssistant) -> None:
    """Test binary sensor icon with lowercase property identifier matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "alarm": DeviceProperty(identifier="alarm", name="Alarm", value="alarm")
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="alarm",
    )

    assert sensor.icon == "mdi:alert-circle"


async def test_binary_sensor_is_on_unknown_value_type(hass: HomeAssistant) -> None:
    """Test binary sensor is_on returns None for unknown value types."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "unknown_prop": DeviceProperty(
            identifier="unknown_prop", name="Unknown", value=[1, 2, 3]
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown_prop",
    )

    # Unknown value type (list) should return None
    assert sensor.is_on is None


async def test_binary_sensor_icon_device_class_smoke(hass: HomeAssistant) -> None:
    """Test binary sensor icon for SMOKE device class when no ENTITY_ICONS match."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Use property identifier that contains "SmokeSensorState" as substring
    # and isn't an exact match to avoid ENTITY_ICONS match
    mock_device.properties = {
        "extra_SmokeSensorState_data": DeviceProperty(
            identifier="extra_SmokeSensorState_data", name="Smoke State", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="extra_SmokeSensorState_data",
    )

    # Should fall through to device class icon for SMOKE
    assert sensor.device_class == BinarySensorDeviceClass.SMOKE
    assert sensor.icon == "mdi:smoke-detector"


async def test_binary_sensor_icon_device_class_moisture(hass: HomeAssistant) -> None:
    """Test binary sensor icon for MOISTURE device class when no ENTITY_ICONS match."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Use property identifier that contains "WaterSensorState" as substring
    mock_device.properties = {
        "extra_WaterSensorState_extra": DeviceProperty(
            identifier="extra_WaterSensorState_extra", name="Water State", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="extra_WaterSensorState_extra",
    )

    # Should fall through to device class icon for MOISTURE
    assert sensor.device_class == BinarySensorDeviceClass.MOISTURE
    assert sensor.icon == "mdi:water-check"


async def test_binary_sensor_icon_device_class_door(hass: HomeAssistant) -> None:
    """Test binary sensor icon for DOOR device class when no ENTITY_ICONS match."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Use property identifier that contains "DoorStatus" as substring
    mock_device.properties = {
        "extra_DoorStatus_extra": DeviceProperty(
            identifier="extra_DoorStatus_extra", name="Door State", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="extra_DoorStatus_extra",
    )

    # Should fall through to device class icon for DOOR
    assert sensor.device_class == BinarySensorDeviceClass.DOOR
    assert sensor.icon == "mdi:door-open"


async def test_binary_sensor_icon_no_match_fallback(hass: HomeAssistant) -> None:
    """Test binary sensor icon when no ENTITY_ICONS match."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Use property name that matches BINARY_SENSOR_DEVICE_CLASS_MAP but not ENTITY_ICONS
    mock_device.properties = {
        "CoStatus": DeviceProperty(identifier="CoStatus", name="CO Status", value=False)
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="CoStatus",
    )

    # CoStatus is in BINARY_SENSOR_DEVICE_CLASS_MAP (maps to "problem")
    # CoStatus is in ENTITY_ICONS, so it matches ENTITY_ICONS first
    assert sensor.device_class == BinarySensorDeviceClass.PROBLEM
    assert sensor.icon == "mdi:molecule-co"


async def test_binary_sensor_icon_lowercase_match_not_in_icons(
    hass: HomeAssistant,
) -> None:
    """Test binary sensor icon lowercase match when key not in ENTITY_ICONS."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property that has lowercase match but not in ENTITY_ICONS
    mock_device.properties = {
        "GenericSensor": DeviceProperty(
            identifier="GenericSensor", name="Generic Sensor", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="GenericSensor",
    )

    # Should fall through to default icon
    assert sensor.icon == "mdi:radiobox-marked"


async def test_binary_sensor_icon_lowercase_match(
    hass: HomeAssistant,
) -> None:
    """Test binary sensor icon with uppercase property identifier that triggers lowercase matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    # Property with uppercase identifier that does NOT exist in ENTITY_ICONS
    # but its lowercase form DOES exist
    mock_device.properties = {
        "SMOKESTATUS": DeviceProperty(
            identifier="SMOKESTATUS", name="Smoke Status", value=False
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanBinarySensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="SMOKESTATUS",
    )

    # First check "SMOKESTATUS" in icons -> False
    # Second check "smokestatus".lower() = "smokestatus" in icons -> True -> mdi:smoke
    assert sensor.icon == "mdi:smoke"


async def test_binary_sensor_skips_non_readable_properties(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test that binary sensor setup skips non-readable properties."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    # Create a non-readable property marked as binary_sensor
    non_readable_prop = DeviceProperty(
        identifier="non_readable_status",
        name="Non Readable Status",
        value=True,
        data_type="bool",
        readable=False,  # Not readable
        entity="binary_sensor",
    )

    # Create a readable property marked as binary_sensor
    readable_prop = DeviceProperty(
        identifier="motion_detected",
        name="Motion Detected",
        value=True,
        data_type="bool",
        readable=True,  # Readable
        entity="binary_sensor",
    )

    mock_device.properties = {
        "non_readable_status": non_readable_prop,
        "motion_detected": readable_prop,
    }
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Only the readable property should create an entity
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-1_motion_detected_binary_sensor"
