"""Common base for entities."""

from pysmarlaapi import Federwiege

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class SmarlaBaseEntity(Entity):
    """Common Base Entity class for defining Smarla device."""

    def __init__(
        self,
        federwiege: Federwiege,
    ) -> None:
        """Initialise the entity."""
        super().__init__()

        self._attr_has_entity_name = True

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, federwiege.serial_number)},
            name="Smarla",
            model="Smarla",
            manufacturer="Swing2Sleep",
            serial_number=federwiege.serial_number,
        )
