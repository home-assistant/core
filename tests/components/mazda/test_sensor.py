"""The sensor tests for the Mazda Connected Services integration."""
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import init_integration


async def test_sensors(hass: HomeAssistant) -> None:
    """Test creation of the sensors."""
    await init_integration(hass)

    entity_registry = er.async_get(hass)

    # Fuel Remaining Percentage
    state = hass.states.get("sensor.my_mazda3_fuel_remaining_percentage")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "My Mazda3 Fuel remaining percentage"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:gas-station"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.state == "87.0"
    entry = entity_registry.async_get("sensor.my_mazda3_fuel_remaining_percentage")
    assert entry
    assert entry.unique_id == "JM000000000000000_fuel_remaining_percentage"

    # Fuel Distance Remaining
    state = hass.states.get("sensor.my_mazda3_fuel_distance_remaining")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Fuel distance remaining"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:gas-station"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DISTANCE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfLength.KILOMETERS
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.state == "381"
    entry = entity_registry.async_get("sensor.my_mazda3_fuel_distance_remaining")
    assert entry
    assert entry.unique_id == "JM000000000000000_fuel_distance_remaining"

    # Odometer
    state = hass.states.get("sensor.my_mazda3_odometer")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Odometer"
    assert state.attributes.get(ATTR_ICON) == "mdi:speedometer"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DISTANCE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfLength.KILOMETERS
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.state == "2795"
    entry = entity_registry.async_get("sensor.my_mazda3_odometer")
    assert entry
    assert entry.unique_id == "JM000000000000000_odometer"

    # Front Left Tire Pressure
    state = hass.states.get("sensor.my_mazda3_front_left_tire_pressure")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Front left tire pressure"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:car-tire-alert"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.KPA
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.state == "241"
    entry = entity_registry.async_get("sensor.my_mazda3_front_left_tire_pressure")
    assert entry
    assert entry.unique_id == "JM000000000000000_front_left_tire_pressure"

    # Front Right Tire Pressure
    state = hass.states.get("sensor.my_mazda3_front_right_tire_pressure")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "My Mazda3 Front right tire pressure"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:car-tire-alert"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.KPA
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.state == "241"
    entry = entity_registry.async_get("sensor.my_mazda3_front_right_tire_pressure")
    assert entry
    assert entry.unique_id == "JM000000000000000_front_right_tire_pressure"

    # Rear Left Tire Pressure
    state = hass.states.get("sensor.my_mazda3_rear_left_tire_pressure")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Rear left tire pressure"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:car-tire-alert"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.KPA
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.state == "228"
    entry = entity_registry.async_get("sensor.my_mazda3_rear_left_tire_pressure")
    assert entry
    assert entry.unique_id == "JM000000000000000_rear_left_tire_pressure"

    # Rear Right Tire Pressure
    state = hass.states.get("sensor.my_mazda3_rear_right_tire_pressure")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Rear right tire pressure"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:car-tire-alert"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.KPA
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.state == "228"
    entry = entity_registry.async_get("sensor.my_mazda3_rear_right_tire_pressure")
    assert entry
    assert entry.unique_id == "JM000000000000000_rear_right_tire_pressure"


async def test_sensors_us_customary_units(hass: HomeAssistant) -> None:
    """Test that the sensors work properly with US customary units."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    await init_integration(hass)

    # In the US, miles are used for vehicle odometers.
    # These tests verify that the unit conversion logic for the distance
    # sensor device class automatically converts the unit to miles.

    # Fuel Distance Remaining
    state = hass.states.get("sensor.my_mazda3_fuel_distance_remaining")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfLength.MILES
    assert state.state == "237"

    # Odometer
    state = hass.states.get("sensor.my_mazda3_odometer")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfLength.MILES
    assert state.state == "1737"


async def test_electric_vehicle_sensors(hass: HomeAssistant) -> None:
    """Test sensors which are specific to electric vehicles."""

    await init_integration(hass, electric_vehicle=True)

    entity_registry = er.async_get(hass)

    # Fuel Remaining Percentage should not exist for an electric vehicle
    entry = entity_registry.async_get("sensor.my_mazda3_fuel_remaining_percentage")
    assert entry is None

    # Fuel Distance Remaining should not exist for an electric vehicle
    entry = entity_registry.async_get("sensor.my_mazda3_fuel_distance_remaining")
    assert entry is None

    # Charge Level
    state = hass.states.get("sensor.my_mazda3_charge_level")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Charge level"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.BATTERY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.state == "80"
    entry = entity_registry.async_get("sensor.my_mazda3_charge_level")
    assert entry
    assert entry.unique_id == "JM000000000000000_ev_charge_level"

    # Remaining Range
    state = hass.states.get("sensor.my_mazda3_remaining_range")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Remaining range"
    assert state.attributes.get(ATTR_ICON) == "mdi:ev-station"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DISTANCE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfLength.KILOMETERS
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.state == "218"
    entry = entity_registry.async_get("sensor.my_mazda3_remaining_range")
    assert entry
    assert entry.unique_id == "JM000000000000000_ev_remaining_range"
