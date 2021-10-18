"""Support for MyQ gateways."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)

from . import MyQEntity
from .const import DOMAIN, MYQ_COORDINATOR, MYQ_GATEWAY


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mysq covers."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    myq = data[MYQ_GATEWAY]
    coordinator = data[MYQ_COORDINATOR]

    entities = []

    for device in myq.gateways.values():
        entities.append(MyQBinarySensorEntity(coordinator, device))

    async_add_entities(entities)


class MyQBinarySensorEntity(MyQEntity, BinarySensorEntity):
    """Representation of a MyQ gateway."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return f"{self._device.name} MyQ Gateway"

    @property
    def is_on(self):
        """Return if the device is online."""
        return super().available

    @property
    def available(self) -> bool:
        """Entity is always available."""
        return True
