"""The binary sensor tests for the Mazda Connected Services integration."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_binary_sensors(hass: HomeAssistant) -> None:
    """Test creation of the binary sensors."""
    await init_integration(hass)

    entity_registry = er.async_get(hass)

    # Driver Door
    state = hass.states.get("binary_sensor.my_mazda3_driver_door")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Driver door"
    assert state.attributes.get(ATTR_ICON) == "mdi:car-door"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.DOOR
    assert state.state == "off"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_driver_door")
    assert entry
    assert entry.unique_id == "JM000000000000000_driver_door"

    # Passenger Door
    state = hass.states.get("binary_sensor.my_mazda3_passenger_door")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Passenger door"
    assert state.attributes.get(ATTR_ICON) == "mdi:car-door"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.DOOR
    assert state.state == "on"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_passenger_door")
    assert entry
    assert entry.unique_id == "JM000000000000000_passenger_door"

    # Rear Left Door
    state = hass.states.get("binary_sensor.my_mazda3_rear_left_door")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Rear left door"
    assert state.attributes.get(ATTR_ICON) == "mdi:car-door"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.DOOR
    assert state.state == "off"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_rear_left_door")
    assert entry
    assert entry.unique_id == "JM000000000000000_rear_left_door"

    # Rear Right Door
    state = hass.states.get("binary_sensor.my_mazda3_rear_right_door")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Rear right door"
    assert state.attributes.get(ATTR_ICON) == "mdi:car-door"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.DOOR
    assert state.state == "off"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_rear_right_door")
    assert entry
    assert entry.unique_id == "JM000000000000000_rear_right_door"

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


async def test_electric_vehicle_binary_sensors(hass: HomeAssistant) -> None:
    """Test sensors which are specific to electric vehicles."""

    await init_integration(hass, electric_vehicle=True)

    entity_registry = er.async_get(hass)

    # Plugged In
    state = hass.states.get("binary_sensor.my_mazda3_plugged_in")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Plugged in"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PLUG
    assert state.state == "on"
    entry = entity_registry.async_get("binary_sensor.my_mazda3_plugged_in")
    assert entry
    assert entry.unique_id == "JM000000000000000_ev_plugged_in"
