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

    # Create a mock config entry and set runtime_data
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id="test_user")
    entry.runtime_data = mock_coordinator

    # Mock async_add_entities callback
    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    # Call sensor setup directly
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

    # Create a mock config entry and set runtime_data
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id="test_user")
    entry.runtime_data = mock_coordinator

    # Mock async_add_entities callback
    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    # Call sensor setup directly
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

    # Create a mock config entry and set runtime_data
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id="test_user")
    entry.runtime_data = mock_coordinator

    # Mock async_add_entities callback
    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    # Call sensor setup directly
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


async def test_sensor_creation_readable_without_entity_marker(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test sensor creation for readable properties without entity marker.

    This tests the else branch in _create_sensors_for_devices that creates
    sensors for readable properties without explicit entity='sensor' marker.
    """
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

    # Create a mock config entry and set runtime_data
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id="test_user")
    entry.runtime_data = mock_coordinator

    # Mock async_add_entities callback
    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    # Call sensor setup directly
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

    # Create a mock config entry and set runtime_data
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id="test_user")
    entry.runtime_data = mock_coordinator

    # Mock async_add_entities callback
    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    # Call sensor setup directly
    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Check that only sensor entity was created (switch and binary_sensor skipped)
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-mixed_temperature_sensor"


async def test_sensor_signal_strength_non_numeric_skips_device_class(
    hass: HomeAssistant,
) -> None:
    """Test signal_strength config skips device class for non-numeric values.

    When signal_strength has a non-numeric value, the sensor should not
    apply the signal_strength device class.
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

    # Should not have signal_strength device class set
    # because value is non-numeric
    assert sensor.device_class != SensorDeviceClass.SIGNAL_STRENGTH


async def test_sensor_skips_non_scalar_properties(hass: HomeAssistant) -> None:
    """Test sensor platform skips bool/list/dict properties.

    This covers sensor.py line 146 where non-scalar properties are filtered out.
    Properties with bool, list, or dict values should not create sensors.
    """
    mock_coordinator = MagicMock()
    mock_device = MagicMock(spec=HeimanDevice)
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"
    mock_device.online = True

    # Create properties of different types
    mock_device.properties = {
        # Valid numeric property - should create sensor
        "temperature": DeviceProperty(
            identifier="temperature",
            name="Temperature",
            value=25.5,
            data_type="float",
            readable=True,
        ),
        # Bool property - should be skipped (line 146)
        "is_active": DeviceProperty(
            identifier="is_active",
            name="Is Active",
            value=True,
            data_type="bool",
            readable=True,
        ),
        # List property - should be skipped (line 146)
        "supported_modes": DeviceProperty(
            identifier="supported_modes",
            name="Supported Modes",
            value=["auto", "manual", "eco"],
            data_type="array",
            readable=True,
        ),
        # Dict property - should be skipped (line 146)
        "config": DeviceProperty(
            identifier="config",
            name="Configuration",
            value={"key1": "value1", "key2": "value2"},
            data_type="object",
            readable=True,
        ),
    }

    mock_coordinator.get_all_devices.return_value = [mock_device]
    mock_coordinator.last_update_success = True
    mock_coordinator.get_device.return_value = mock_device
    mock_coordinator.async_add_listener = MagicMock()

    # Create a mock config entry and set runtime_data
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id="test_user")
    entry.runtime_data = mock_coordinator

    # Mock async_add_entities callback
    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    # Call sensor setup directly
    await async_setup_entry(hass, entry, async_add_entities)
    await hass.async_block_till_done()

    # Only the numeric temperature property should create a sensor
    # Bool, list, and dict properties should be filtered out (line 146)
    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "device-1_temperature_sensor"
    assert added_entities[0]._property_identifier == "temperature"

