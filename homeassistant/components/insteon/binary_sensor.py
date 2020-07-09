"""Support for INSTEON dimmers via PowerLinc Modem."""
import logging

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
    DOMAIN,
    BinarySensorEntity,
)

from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the INSTEON entity class for the hass platform."""
    async_add_insteon_entities(
        hass, DOMAIN, InsteonBinarySensorEntity, async_add_entities, discovery_info
    )


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
