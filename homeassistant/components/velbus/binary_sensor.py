"""Support for Velbus Binary Sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity

from . import VelbusEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("binary_sensor"):
        entities.append(VelbusBinarySensor(channel))
    async_add_entities(entities)


class VelbusBinarySensor(VelbusEntity, BinarySensorEntity):
    """Representation of a Velbus Binary Sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if the sensor is on."""
        return self._channel.is_closed()
