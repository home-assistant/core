"""The Minecraft Server binary sensor platform."""

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorDevice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import MinecraftServer, MinecraftServerEntity
from .const import DOMAIN, ICON_STATUS, NAME_STATUS


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Minecraft Server binary sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    # Create entities list.
    entities = [MinecraftServerStatusBinarySensor(server)]

    # Add binary sensor entities.
    async_add_entities(entities, True)


class MinecraftServerStatusBinarySensor(MinecraftServerEntity, BinarySensorDevice):
    """Representation of a Minecraft Server status binary sensor."""

    def __init__(self, server: MinecraftServer) -> None:
        """Initialize status binary sensor."""
        super().__init__(
            server=server,
            type_name=NAME_STATUS,
            icon=ICON_STATUS,
            device_class=DEVICE_CLASS_CONNECTIVITY,
        )
        self._is_on = False

    @property
    def is_on(self) -> bool:
        """Return binary state."""
        return self._is_on

    async def async_update(self) -> None:
        """Update status."""
        self._is_on = self._server.online
