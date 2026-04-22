"""Tests for the Heiman Home sensor platform."""

from unittest.mock import MagicMock, patch

from heimanconnect import DeviceProperty, HeimanDevice

from homeassistant.components.heiman_home.const import DOMAIN
from homeassistant.components.heiman_home.sensor import (
    HeimanSensorEntity,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensor_setup(hass: HomeAssistant, setup_credentials: None) -> None:
    """Test sensor platform setup."""
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


async def test_sensor_entity_creation(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test sensor entity creation from device properties."""
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

    # Create mock coordinator with device
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

    temp_prop = DeviceProperty(
        identifier="temperature",
        name="Temperature",
        value=25.5,
        data_type="float",
        unit="°C",
        readable=True,
        entity="sensor",
    )

    mock_device.properties = {"temperature": temp_prop}
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    # Mock async_add_entities callback
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

    # Replace coordinator with mock
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call sensor setup
    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Check that sensor entity was created
    assert len(added_entities) == 1
    sensor = added_entities[0]
    assert sensor.unique_id == "device-1_temperature_sensor"
    assert sensor.name == "Temperature"


async def test_sensor_entity_available_property(hass: HomeAssistant) -> None:
    """Test sensor entity available property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.5
        )
    }

    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Test available when device is online
    assert sensor.available is True

    # Test not available when device is offline
    mock_device.online = False
    assert sensor.available is False

    # Test not available when device is not found
    mock_coordinator.get_device.return_value = None
    assert sensor.available is False

    # Test not available when last update failed
    mock_device.online = True
    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.last_update_success = False
    assert sensor.available is False


async def test_sensor_entity_native_value(hass: HomeAssistant) -> None:
    """Test sensor entity native_value property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=25.5
        ),
        "humidity": DeviceProperty(identifier="humidity", name="Humidity", value=60.0),
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Test getting value
    assert sensor.native_value == 25.5

    # Test when device is not found
    mock_coordinator.get_device.return_value = None
    assert sensor.native_value is None

    # Test when property is not found
    mock_coordinator.get_device.return_value = mock_device
    sensor2 = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="non_existent",
    )
    assert sensor2.native_value is None


async def test_sensor_entity_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test sensor entity extra_state_attributes property."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            unit="°C",
            data_type="float",
        ),
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Test extra attributes
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs.get("unit") == "°C"
    assert attrs.get("data_type") == "float"

    # Test when device is not found
    mock_coordinator.get_device.return_value = None
    attrs = sensor.extra_state_attributes
    assert attrs == {}


async def test_sensor_apply_sensor_config_temperature(hass: HomeAssistant) -> None:
    """Test sensor configuration for temperature."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Check device class and unit
    assert sensor.device_class == SensorDeviceClass.TEMPERATURE
    assert sensor.native_unit_of_measurement == "°C"
    assert sensor.state_class == SensorStateClass.MEASUREMENT


async def test_sensor_apply_sensor_config_humidity(hass: HomeAssistant) -> None:
    """Test sensor configuration for humidity."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "humidity": DeviceProperty(
            identifier="humidity",
            name="Humidity",
            value=60.0,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="humidity",
    )

    # Check device class and unit
    assert sensor.device_class == SensorDeviceClass.HUMIDITY
    assert sensor.native_unit_of_measurement == "%"
    assert sensor.state_class == SensorStateClass.MEASUREMENT


async def test_sensor_apply_sensor_config_battery(hass: HomeAssistant) -> None:
    """Test sensor configuration for battery."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "battery": DeviceProperty(
            identifier="battery",
            name="Battery",
            value=85,
            data_type="int",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="battery",
    )

    # Check device class and unit
    assert sensor.device_class == SensorDeviceClass.BATTERY
    assert sensor.native_unit_of_measurement == "%"
    assert sensor.state_class == SensorStateClass.MEASUREMENT


async def test_sensor_apply_sensor_config_numeric(hass: HomeAssistant) -> None:
    """Test sensor configuration for numeric values."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "pressure": DeviceProperty(
            identifier="pressure",
            name="Pressure",
            value=1013.25,
            data_type="double",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="pressure",
    )

    # Numeric sensors should have state_class
    assert sensor.state_class == SensorStateClass.MEASUREMENT


async def test_sensor_apply_sensor_config_non_numeric(hass: HomeAssistant) -> None:
    """Test sensor configuration for non-numeric values."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "status": DeviceProperty(
            identifier="status",
            name="Status",
            value="online",
            data_type="string",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="status",
    )

    # Non-numeric sensors should not have state_class
    assert not hasattr(sensor, "state_class") or sensor.state_class is None


async def test_sensor_apply_icon_temperature(hass: HomeAssistant) -> None:
    """Test icon application for temperature sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Check icon for temperature
    assert sensor.icon == "mdi:thermometer"


async def test_sensor_apply_icon_humidity(hass: HomeAssistant) -> None:
    """Test icon application for humidity sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "humidity": DeviceProperty(
            identifier="humidity",
            name="Humidity",
            value=60.0,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="humidity",
    )

    # Check icon for humidity
    assert sensor.icon == "mdi:water-percent"


async def test_sensor_apply_icon_battery(hass: HomeAssistant) -> None:
    """Test icon application for battery sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "battery": DeviceProperty(
            identifier="battery",
            name="Battery",
            value=85,
            data_type="int",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="battery",
    )

    # Check icon for battery
    assert sensor.icon == "mdi:battery"


async def test_sensor_apply_icon_signal_strength(hass: HomeAssistant) -> None:
    """Test icon application for signal strength sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "RSSI": DeviceProperty(
            identifier="RSSI",
            name="Signal Strength",
            value=-60,
            data_type="int",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="RSSI",
    )

    # Check icon for signal strength
    assert sensor.icon == "mdi:signal"


async def test_sensor_apply_icon_default(hass: HomeAssistant) -> None:
    """Test default icon application for unknown sensor type."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "unknown": DeviceProperty(
            identifier="unknown",
            name="Unknown Sensor",
            value=100,
            data_type="int",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="unknown",
    )

    # Check default icon
    assert sensor.icon == "mdi:gauge"


async def test_sensor_entity_device_info(hass: HomeAssistant) -> None:
    """Test sensor entity device info."""
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
    # Ensure device_info is not set to avoid conflict with sensor's device_info
    mock_device.device_info = None
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Check device info
    device_info = sensor.device_info
    assert device_info is not None
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "Heiman"
    assert device_info["model"] == "HS1"
    assert device_info["sw_version"] == "1.0"
    assert device_info["hw_version"] == "1.0"
    assert (DOMAIN, "device-1") in device_info["identifiers"]


async def test_sensor_entity_unique_id(hass: HomeAssistant) -> None:
    """Test sensor entity unique ID."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-123"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Check unique ID
    assert sensor.unique_id == "device-123_temperature_sensor"


async def test_sensor_entity_has_entity_name(hass: HomeAssistant) -> None:
    """Test sensor entity has entity name."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "My Gateway"
    mock_device.online = True
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Check has_entity_name
    assert sensor.has_entity_name is True


async def test_sensor_entity_creation_with_multiple_properties(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test sensor entity creation with multiple readable properties."""
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

    # Create mock coordinator with device with multiple properties
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Multi Sensor Device"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS2"
    mock_device.product_id = "prod-2"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    temp_prop = DeviceProperty(
        identifier="temperature",
        name="Temperature",
        value=25.5,
        data_type="float",
        unit="°C",
        readable=True,
        entity="sensor",
    )

    humidity_prop = DeviceProperty(
        identifier="humidity",
        name="Humidity",
        value=60.0,
        data_type="float",
        unit="%",
        readable=True,
        entity="sensor",
    )

    battery_prop = DeviceProperty(
        identifier="battery",
        name="Battery",
        value=85,
        data_type="int",
        unit="%",
        readable=True,
        entity="sensor",
    )

    not_readable_prop = DeviceProperty(
        identifier="internal_state",
        name="Internal State",
        value="active",
        data_type="string",
        readable=False,
    )

    mock_device.properties = {
        "temperature": temp_prop,
        "humidity": humidity_prop,
        "battery": battery_prop,
        "internal_state": not_readable_prop,
    }
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    # Mock async_add_entities callback
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

    # Replace coordinator with mock
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call sensor setup
    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Check that only readable properties with entity="sensor" were created
    assert len(added_entities) == 3
    unique_ids = {sensor.unique_id for sensor in added_entities}
    assert "device-1_temperature_sensor" in unique_ids
    assert "device-1_humidity_sensor" in unique_ids
    assert "device-1_battery_sensor" in unique_ids


async def test_sensor_entity_creation_no_readable_properties(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test sensor entity creation with no readable properties."""
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

    # Create mock coordinator with device without readable properties
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

    # Mock async_add_entities callback
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

    # Replace coordinator with mock
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call sensor setup
    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # No sensors should be created
    assert len(added_entities) == 0


async def test_sensor_extra_state_attributes_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Test extra_state_attributes when device is not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            unit="°C",
            data_type="float",
        ),
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Get attributes normally
    attrs = sensor.extra_state_attributes
    assert attrs.get("unit") == "°C"
    assert attrs.get("data_type") == "float"

    # When device is not found
    mock_coordinator.get_device.return_value = None
    attrs = sensor.extra_state_attributes
    assert attrs == {}


async def test_sensor_extra_state_attributes_property_not_found(
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

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # When property is not found
    attrs = sensor.extra_state_attributes
    assert attrs == {}


async def test_sensor_apply_sensor_config_voltage(hass: HomeAssistant) -> None:
    """Test sensor configuration for voltage."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "voltage": DeviceProperty(
            identifier="voltage",
            name="Voltage",
            value=220.0,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="voltage",
    )

    # Check device class and unit
    assert sensor.device_class == SensorDeviceClass.VOLTAGE
    assert sensor.native_unit_of_measurement == "V"
    assert sensor.state_class == SensorStateClass.MEASUREMENT


async def test_sensor_apply_sensor_config_power(hass: HomeAssistant) -> None:
    """Test sensor configuration for power."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power": DeviceProperty(
            identifier="power",
            name="Power",
            value=100.0,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power",
    )

    # Check device class and unit
    assert sensor.device_class == SensorDeviceClass.POWER
    assert sensor.native_unit_of_measurement == "W"
    assert sensor.state_class == SensorStateClass.MEASUREMENT


async def test_sensor_apply_sensor_config_energy(hass: HomeAssistant) -> None:
    """Test sensor configuration for energy."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "energy": DeviceProperty(
            identifier="energy",
            name="Energy",
            value=10.5,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="energy",
    )

    # Check device class and unit
    assert sensor.device_class == SensorDeviceClass.ENERGY
    assert sensor.native_unit_of_measurement == "kWh"
    assert sensor.state_class == SensorStateClass.TOTAL_INCREASING


async def test_sensor_apply_sensor_config_co_concentration(hass: HomeAssistant) -> None:
    """Test sensor configuration for CO concentration."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "co_concentration": DeviceProperty(
            identifier="co_concentration",
            name="CO Concentration",
            value=25,
            data_type="int",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="co_concentration",
    )

    # Check device class
    assert sensor.device_class == SensorDeviceClass.CO


async def test_sensor_apply_icon_voltage(hass: HomeAssistant) -> None:
    """Test icon application for voltage sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "voltage": DeviceProperty(
            identifier="voltage",
            name="Voltage",
            value=220.0,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="voltage",
    )

    # Check icon for voltage
    assert sensor.icon == "mdi:flash-triangle"


async def test_sensor_apply_icon_power(hass: HomeAssistant) -> None:
    """Test icon application for power sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "power": DeviceProperty(
            identifier="power",
            name="Power",
            value=100.0,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power",
    )

    # Check icon for power
    assert sensor.icon == "mdi:flash"


async def test_sensor_apply_icon_energy(hass: HomeAssistant) -> None:
    """Test icon application for energy sensor."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "energy": DeviceProperty(
            identifier="energy",
            name="Energy",
            value=10.5,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="energy",
    )

    # Check icon for energy
    assert sensor.icon == "mdi:lightning-bolt"


async def test_sensor_native_value_none(hass: HomeAssistant) -> None:
    """Test sensor entity native_value when property value is None."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature", name="Temperature", value=None
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Test None value
    assert sensor.native_value is None


async def test_sensor_apply_icon_lowercase_matching(hass: HomeAssistant) -> None:
    """Test icon application with lowercase property identifier matching."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "Temperature": DeviceProperty(
            identifier="Temperature",
            name="Temperature",
            value=25.5,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="Temperature",
    )

    # Check icon - should match via lowercase fallback
    assert sensor.icon == "mdi:thermometer"


async def test_sensor_apply_icon_temperature_default(hass: HomeAssistant) -> None:
    """Test default icon for temperature when icon config not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "temperature_value": DeviceProperty(
            identifier="temperature_value",
            name="Temperature Value",
            value=25.5,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature_value",
    )

    # Check device class is set to temperature for temperature_value
    assert sensor.device_class == SensorDeviceClass.TEMPERATURE
    # Should use default icon for temperature device class (not in ENTITY_ICONS)
    assert sensor.icon == "mdi:thermometer"


async def test_sensor_apply_icon_humidity_default(hass: HomeAssistant) -> None:
    """Test default icon for humidity when icon config not found."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True
    mock_device.properties = {
        "humidity_value": DeviceProperty(
            identifier="humidity_value",
            name="Humidity Value",
            value=60.0,
            data_type="float",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="humidity_value",
    )

    # Check device class is set to humidity for humidity_value
    assert sensor.device_class == SensorDeviceClass.HUMIDITY
    # Should use default icon for humidity device class (not in ENTITY_ICONS)
    assert sensor.icon == "mdi:water-percent"


async def test_sensor_creation_readable_without_entity_marker(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test sensor creation for readable properties without entity marker.

    This tests the else branch in _create_sensors_for_devices that creates
    sensors for readable properties without explicit entity='sensor' marker.
    """
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

    # Create mock coordinator with device that has properties without entity marker
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-no-entity"
    mock_device.device_name = "Device Without Entity Marker"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    # Property without entity attribute at all (tests else branch at line 65)
    no_entity_prop = DeviceProperty(
        identifier="signal_strength",
        name="Signal Strength",
        value=-60,
        data_type="int",
        readable=True,
        # Note: no 'entity' attribute set
    )

    # Property with entity=None (should also create sensor)
    entity_none_prop = DeviceProperty(
        identifier="rssi_value",
        name="RSSI Value",
        value=-65,
        data_type="int",
        readable=True,
        entity=None,
    )

    mock_device.properties = {
        "signal_strength": no_entity_prop,
        "rssi_value": entity_none_prop,
    }
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    # Mock async_add_entities callback
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

    # Replace coordinator with mock
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call sensor setup
    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Check that sensors were created for properties without entity marker
    assert len(added_entities) == 2
    unique_ids = {sensor.unique_id for sensor in added_entities}
    assert "device-no-entity_signal_strength_sensor" in unique_ids
    assert "device-no-entity_rssi_value_sensor" in unique_ids


async def test_sensor_creation_skips_non_sensor_entities(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test sensor creation skips properties with non-sensor entity markers.

    This tests the elif branch that skips properties explicitly assigned
    to different entity platforms.
    """
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

    # Create mock coordinator with device that has properties with different entity types
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-mixed"
    mock_device.device_name = "Device With Mixed Entities"
    mock_device.manufacturer = "Heiman"
    mock_device.model = "HS1"
    mock_device.product_id = "prod-1"
    mock_device.firmware_version = "1.0"
    mock_device.hardware_version = "1.0"
    mock_device.online = True

    # Property with entity='switch' - should be skipped
    switch_prop = DeviceProperty(
        identifier="switch_state",
        name="Switch State",
        value="on",
        data_type="string",
        readable=True,
        entity="switch",
    )

    # Property with entity='binary_sensor' - should be skipped
    binary_sensor_prop = DeviceProperty(
        identifier="motion_detected",
        name="Motion Detected",
        value=True,
        data_type="bool",
        readable=True,
        entity="binary_sensor",
    )

    # Property with entity='sensor' - should be created
    sensor_prop = DeviceProperty(
        identifier="temperature",
        name="Temperature",
        value=25.0,
        data_type="float",
        readable=True,
        entity="sensor",
    )

    mock_device.properties = {
        "switch_state": switch_prop,
        "motion_detected": binary_sensor_prop,
        "temperature": sensor_prop,
    }
    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device

    # Mock async_add_entities callback
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

    # Replace coordinator with mock
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call sensor setup
    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Check that only sensor entity was created (switch and binary_sensor skipped)
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-mixed_temperature_sensor"


async def test_sensor_signal_strength_non_numeric_skips_device_class(
    hass: HomeAssistant,
) -> None:
    """Test signal_strength config skips device class for non-numeric values.

    This tests lines 229-230 where non-numeric signal_strength values
    don't get the device class applied.
    """
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True

    # Signal strength with string value (non-numeric)
    mock_device.properties = {
        "signal_strength": DeviceProperty(
            identifier="signal_strength",
            name="Signal Strength",
            value="excellent",  # Non-numeric string
            data_type="string",  # String data type
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="signal_strength",
    )

    # Should not have signal_strength device class set (lines 229-230)
    # because value is non-numeric
    assert sensor.device_class != SensorDeviceClass.SIGNAL_STRENGTH


async def test_sensor_native_value_non_numeric_for_device_class(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test native_value returns None for non-numeric values with numeric device class.

    This tests lines 333-341 where native_value returns None when
    the value type doesn't match the device class expectations.
    """
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True

    # Create a sensor with numeric device class but string value
    mock_device.properties = {
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value="hot",  # String value for numeric device class
            data_type="string",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="temperature",
    )

    # Manually set device class to temperature to trigger the check
    sensor._attr_device_class = SensorDeviceClass.TEMPERATURE

    # native_value should return None and log warning (lines 333-341)
    result = sensor.native_value

    # Should return None for non-numeric value with numeric device class
    assert result is None
    # Warning should be logged
    assert "non-numeric" in caplog.text.lower() or "validation error" in caplog.text.lower()


async def test_sensor_native_value_bool_for_numeric_device_class(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test native_value returns None for boolean values with numeric device class.

    This tests the bool check in lines 330-331.
    """
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True

    # Create a sensor with numeric device class but boolean value
    mock_device.properties = {
        "battery": DeviceProperty(
            identifier="battery",
            name="Battery",
            value=True,  # Boolean value
            data_type="bool",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="battery",
    )

    # Manually set device class to battery to trigger the check
    sensor._attr_device_class = SensorDeviceClass.BATTERY

    # native_value should return None (lines 330-331)
    result = sensor.native_value

    # Should return None for boolean value with numeric device class
    assert result is None


async def test_sensor_native_value_list_for_numeric_device_class(
    hass: HomeAssistant,
) -> None:
    """Test native_value returns None for list values with numeric device class.

    This tests line 331 where list type is rejected.
    """
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True

    # Create a sensor with numeric device class but list value
    mock_device.properties = {
        "power": DeviceProperty(
            identifier="power",
            name="Power",
            value=[100, 200],  # List value
            data_type="array",
            readable=True,
        )
    }

    mock_coordinator.get_device.return_value = mock_device

    sensor = HeimanSensorEntity(
        coordinator=mock_coordinator,
        device=mock_device,
        property_identifier="power",
    )

    # Manually set device class to power to trigger the check
    sensor._attr_device_class = SensorDeviceClass.POWER

    # native_value should return None
    result = sensor.native_value

    # Should return None for list value with numeric device class
    assert result is None
