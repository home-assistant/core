"""Support for MyQ gateways."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyQEntity
from .const import DOMAIN, MYQ_COORDINATOR, MYQ_GATEWAY


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
