"""
Test for the SmartThings sensors platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import ATTRIBUTES, CAPABILITIES, Attribute, Capability

from homeassistant.components.sensor import DEVICE_CLASSES, DOMAIN as SENSOR_DOMAIN
from homeassistant.components.smartthings import sensor
from homeassistant.components.smartthings.const import (
    DOMAIN,
    POWER_CONSUMPTION_REPORT_NAMES,
    SIGNAL_SMARTTHINGS_UPDATE,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_ENERGY,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
<<<<<<< HEAD
    STATE_UNAVAILABLE,
    POWER_WATT,
=======
>>>>>>> One sensor for report; shows energy as state
    STATE_UNKNOWN,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


async def test_mapping_integrity():
    """Test ensures the map dicts have proper integrity."""
    for capability, maps in sensor.CAPABILITY_TO_SENSORS.items():
        assert capability in CAPABILITIES, capability
        for sensor_map in maps:
            assert sensor_map.attribute in ATTRIBUTES, sensor_map.attribute
            if sensor_map.device_class:
                assert (
                    sensor_map.device_class in DEVICE_CLASSES
                ), sensor_map.device_class


async def test_entity_state(hass, device_factory):
    """Tests the state attributes properly match the sensor types."""
    device = device_factory("Sensor 1", [Capability.battery], {Attribute.battery: 100})
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    state = hass.states.get("sensor.sensor_1_battery")
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{device.label} Battery"


async def test_entity_three_axis_state(hass, device_factory):
    """Tests the state attributes properly match the three axis types."""
    device = device_factory(
        "Three Axis", [Capability.three_axis], {Attribute.three_axis: [100, 75, 25]}
    )
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    state = hass.states.get("sensor.three_axis_x_coordinate")
    assert state.state == "100"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{device.label} X Coordinate"
    state = hass.states.get("sensor.three_axis_y_coordinate")
    assert state.state == "75"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{device.label} Y Coordinate"
    state = hass.states.get("sensor.three_axis_z_coordinate")
    assert state.state == "25"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{device.label} Z Coordinate"


async def test_entity_three_axis_invalid_state(hass, device_factory):
    """Tests the state attributes properly match the three axis types."""
    device = device_factory(
        "Three Axis", [Capability.three_axis], {Attribute.three_axis: []}
    )
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    state = hass.states.get("sensor.three_axis_x_coordinate")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.three_axis_y_coordinate")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.three_axis_z_coordinate")
    assert state.state == STATE_UNKNOWN


async def test_entity_power_consumption_report_state(hass, device_factory):
    """Test the state attributes."""
    mock_report = {
        "start": "00110501T000000-0800",  # Nov 5 2020 America/Los Angeles
        "power": 90,
        "energy": 10000.0,  # primary attribute, reported by state of sensor
        "end": "00110601T000000-0800",  # Nov 6 2020 America/Los Angeles
        "deltaEnergy": 100.0,
        "powerEnergy": 80.0,
        "energySaved": 300.0,
        "persistedEnergy": 20000.0,
    }
    device = device_factory(
        "Appliance",
        [Capability.power_consumption_report],
        {Attribute.power_consumption: mock_report},
    )
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    state = hass.states.get("sensor.appliance_power_consumption_report")
    assert state.state == "10000.0"
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == f"{device.label} Power Consumption Report"
    )
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ENERGY_WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_ENERGY
    attributes = POWER_CONSUMPTION_REPORT_NAMES.values()
    mock_report = {k: v for k, v in mock_report.items() if k != "energy"}
    for attribute, mock_value in zip(attributes, mock_report.values()):
        assert state.attributes[attribute] == mock_value


async def test_entity_power_consumption_report_invalid_state(hass, device_factory):
    """Test the state attributes."""
    device = device_factory(
        "Appliance",
        [Capability.power_consumption_report],
        {Attribute.power_consumption: {}},
    )
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    state = hass.states.get("sensor.appliance_power_consumption_report")
    assert state.state == STATE_UNKNOWN


async def test_entity_and_device_attributes(hass, device_factory):
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory("Sensor 1", [Capability.battery], {Attribute.battery: 100})
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Act
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    # Assert
    entry = entity_registry.async_get("sensor.sensor_1_battery")
    assert entry
    assert entry.unique_id == f"{device.device_id}.{Attribute.battery}"
    entry = device_registry.async_get_device({(DOMAIN, device.device_id)})
    assert entry
    assert entry.name == device.label
    assert entry.model == device.device_type_name
    assert entry.manufacturer == "Unavailable"


async def test_update_from_signal(hass, device_factory):
    """Test the binary_sensor updates when receiving a signal."""
    # Arrange
    device = device_factory("Sensor 1", [Capability.battery], {Attribute.battery: 100})
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    device.status.apply_attribute_update(
        "main", Capability.battery, Attribute.battery, 75
    )
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("sensor.sensor_1_battery")
    assert state is not None
    assert state.state == "75"


async def test_unload_config_entry(hass, device_factory):
    """Test the binary_sensor is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory("Sensor 1", [Capability.battery], {Attribute.battery: 100})
    config_entry = await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    # Assert
    assert hass.states.get("sensor.sensor_1_battery").state == STATE_UNAVAILABLE
