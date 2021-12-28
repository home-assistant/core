"""Support for Big Ass Fans SenseME occupancy sensor."""
import logging

from aiosenseme import SensemeDevice

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE

from . import SensemeEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SenseME occupancy sensors."""
    device = hass.data[DOMAIN][entry.entry_id][CONF_DEVICE]
    if device.has_sensor:
        async_add_entities([HASensemeOccupancySensor(device)])


class HASensemeOccupancySensor(SensemeEntity, BinarySensorEntity):
    """Representation of a Big Ass Fans SenseME occupancy sensor."""

    def __init__(self, device: SensemeDevice) -> None:
        """Initialize the entity."""
        super().__init__(device, f"{device.name} Occupancy")

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this sensor."""
        return f"{self._device.uuid}-SENSOR"

    @property
    def is_on(self) -> bool:
        """Return True if sensor is occupied."""
        return self._device.motion_detected

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return DEVICE_CLASS_OCCUPANCY
