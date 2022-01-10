"""Support for Abode Security System binary sensors."""
import abodepy.helpers.constants as CONST

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AbodeDevice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Abode binary sensor devices."""
    data = hass.data[DOMAIN]

    device_types = [
        CONST.TYPE_CONNECTIVITY,
        CONST.TYPE_MOISTURE,
        CONST.TYPE_MOTION,
        CONST.TYPE_OCCUPANCY,
        CONST.TYPE_OPENING,
    ]

    entities = []

    for device in data.abode.get_devices(generic_type=device_types):
        entities.append(AbodeBinarySensor(data, device))

    async_add_entities(entities)


class AbodeBinarySensor(AbodeDevice, BinarySensorEntity):
    """A binary sensor implementation for Abode device."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._device.is_on

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        if self._device.get_value("is_window") == "1":
            return BinarySensorDeviceClass.WINDOW
        return self._device.generic_type
