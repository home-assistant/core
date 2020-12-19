"""Support for INSTEON dimmers via PowerLinc Modem."""
from pyinsteon.groups import (
    CO_SENSOR,
    DOOR_SENSOR,
    HEARTBEAT,
    LEAK_SENSOR_WET,
    LIGHT_SENSOR,
    LOW_BATTERY,
    MOTION_SENSOR,
    OPEN_CLOSE_SENSOR,
    SENSOR_MALFUNCTION,
    SMOKE_SENSOR,
    TEST_SENSOR,
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_LIGHT,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_SMOKE,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

SENSOR_TYPES = {
    OPEN_CLOSE_SENSOR: DEVICE_CLASS_OPENING,
    MOTION_SENSOR: DEVICE_CLASS_MOTION,
    DOOR_SENSOR: DEVICE_CLASS_DOOR,
    LEAK_SENSOR_WET: DEVICE_CLASS_MOISTURE,
    LIGHT_SENSOR: DEVICE_CLASS_LIGHT,
    LOW_BATTERY: DEVICE_CLASS_BATTERY,
    CO_SENSOR: DEVICE_CLASS_GAS,
    SMOKE_SENSOR: DEVICE_CLASS_SMOKE,
    TEST_SENSOR: DEVICE_CLASS_SAFETY,
    SENSOR_MALFUNCTION: DEVICE_CLASS_PROBLEM,
    HEARTBEAT: DEVICE_CLASS_PROBLEM,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Insteon binary sensors from a config entry."""

    def add_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass,
            BINARY_SENSOR_DOMAIN,
            InsteonBinarySensorEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{BINARY_SENSOR_DOMAIN}"
    async_dispatcher_connect(hass, signal, add_entities)
    add_entities()


class InsteonBinarySensorEntity(InsteonEntity, BinarySensorEntity):
    """A Class for an Insteon binary sensor entity."""

    def __init__(self, device, group):
        """Initialize the INSTEON binary sensor."""
        super().__init__(device, group)
        self._sensor_type = SENSOR_TYPES.get(self._insteon_device_group.name)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return bool(self._insteon_device_group.value)
