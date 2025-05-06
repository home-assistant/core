"""Common base for entities."""

from typing import Any

from pysmarlaapi import Federwiege
from pysmarlaapi.federwiege.classes import Property

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DEVICE_MODEL_NAME, DOMAIN, MANUFACTURER_NAME


class SmarlaBaseEntity(Entity):
    """Common Base Entity class for defining Smarla device."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, federwiege: Federwiege, prop: Property) -> None:
        """Initialise the entity."""
        self._property = prop
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, federwiege.serial_number)},
            name=DEVICE_MODEL_NAME,
            model=DEVICE_MODEL_NAME,
            manufacturer=MANUFACTURER_NAME,
            serial_number=federwiege.serial_number,
        )

    async def on_change(self, value: Any):
        """Notify ha when state changes."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await self._property.add_listener(self.on_change)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        await self._property.remove_listener(self.on_change)
