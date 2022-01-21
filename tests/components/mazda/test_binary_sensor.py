"""The binary sensor tests for the Mazda Connected Services integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_binary_sensors(hass):
    """Test creation of the binary sensors."""
    await init_integration(hass)

    entity_registry = er.async_get(hass)

    # Doors
    state = hass.states.get("binary_sensor.my_mazda3_doors")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Doors"
    assert state.attributes.get(ATTR_ICON) == "mdi:car-door"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.DOOR
    assert not state.attributes.get("driver_door_open")
    assert state.attributes.get("passenger_door_open")
    assert not state.attributes.get("rear_left_door_open")
    assert not state.attributes.get("rear_right_door_open")
    assert state.state == "on"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_doors")
    assert entry
    assert entry.unique_id == "JM000000000000000_doors"

    # Trunk
    state = hass.states.get("binary_sensor.my_mazda3_trunk")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Trunk"
    assert state.attributes.get(ATTR_ICON) == "mdi:car-back"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.DOOR
    assert state.state == "off"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_trunk")
    assert entry
    assert entry.unique_id == "JM000000000000000_trunk"

    # Hood
    state = hass.states.get("binary_sensor.my_mazda3_hood")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Hood"
    assert state.attributes.get(ATTR_ICON) == "mdi:car"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.DOOR
    assert state.state == "on"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_hood")
    assert entry
    assert entry.unique_id == "JM000000000000000_hood"


async def test_electric_vehicle_binary_sensors(hass):
    """Test sensors which are specific to electric vehicles."""

    await init_integration(hass, electric_vehicle=True)

    entity_registry = er.async_get(hass)

    # Plugged In
    state = hass.states.get("binary_sensor.my_mazda3_plugged_in")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Plugged In"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PLUG
    assert state.state == "on"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_plugged_in")
    assert entry
    assert entry.unique_id == "JM000000000000000_ev_plugged_in"

    # Charging
    state = hass.states.get("binary_sensor.my_mazda3_charging")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Charging"
    assert (
        state.attributes.get(ATTR_DEVICE_CLASS)
        == BinarySensorDeviceClass.BATTERY_CHARGING
    )
    assert state.state == "on"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_charging")
    assert entry
    assert entry.unique_id == "JM000000000000000_ev_charging"
