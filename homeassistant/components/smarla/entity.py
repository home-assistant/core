"""Common base for entities."""

from pysmarlaapi import Federwiege

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DEVICE_MODEL_NAME, DOMAIN, MANUFACTURER_NAME


class SmarlaBaseEntity(Entity):
    """Common Base Entity class for defining Smarla device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        federwiege: Federwiege,
    ) -> None:
        """Initialise the entity."""
        super().__init__()

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, federwiege.serial_number)},
            name=DEVICE_MODEL_NAME,
            model=DEVICE_MODEL_NAME,
            manufacturer=MANUFACTURER_NAME,
            serial_number=federwiege.serial_number,
        )
