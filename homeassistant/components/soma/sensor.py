"""Support for Soma sensors."""
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.helpers.entity import Entity

from . import DEVICES, SomaEntity
from .const import API, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Soma sensor platform."""

    devices = hass.data[DOMAIN][DEVICES]

    async_add_entities(
        [SomaSensor(sensor, hass.data[DOMAIN][API]) for sensor in devices], True
    )


class SomaSensor(SomaEntity, Entity):
    """Representation of a Soma cover device."""

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_BATTERY

    @property
    def name(self):
        """Return the name of the device."""
        return self.device["name"] + " battery level"

    @property
    def state(self):
        """Return the state of the entity."""
        return self.battery_state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return PERCENTAGE
