"""The FiveM binary sensor platform."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FiveMEntity, FiveMServer
from .const import DOMAIN, ICON_STATUS, NAME_STATUS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FiveM binary sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    entities = [FiveMStatusBinarySensor(server)]

    async_add_entities(entities, True)


class FiveMStatusBinarySensor(FiveMEntity, BinarySensorEntity):
    """Representation of a FiveM status binary sensor."""

    def __init__(self, fivem: FiveMServer) -> None:
        """Initialize status binary sensor."""
        super().__init__(
            fivem, NAME_STATUS, ICON_STATUS, BinarySensorDeviceClass.CONNECTIVITY
        )
        self._is_on = self._fivem.online

    @property
    def is_on(self) -> bool:
        """Return binary state."""
        return self._is_on

    async def async_update(self) -> None:
        """Update status."""
        self._is_on = self._fivem.online
