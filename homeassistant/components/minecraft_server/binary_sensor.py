"""The Minecraft Server binary sensor platform."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinecraftServer
from .const import DOMAIN, ICON_STATUS, NAME_STATUS
from .entity import MinecraftServerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Minecraft Server binary sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    # Create entities list.
    entities = [MinecraftServerStatusBinarySensor(server)]

    # Add binary sensor entities.
    async_add_entities(entities, True)


class MinecraftServerStatusBinarySensor(MinecraftServerEntity, BinarySensorEntity):
    """Representation of a Minecraft Server status binary sensor."""

    _attr_translation_key = "status"

    def __init__(self, server: MinecraftServer) -> None:
        """Initialize status binary sensor."""
        super().__init__(
            server=server,
            type_name=NAME_STATUS,
            icon=ICON_STATUS,
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )
        self._attr_is_on = False

    async def async_update(self) -> None:
        """Update status."""
        self._attr_is_on = self._server.online
