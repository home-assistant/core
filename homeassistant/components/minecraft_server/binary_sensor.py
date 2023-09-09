"""The Minecraft Server binary sensor platform."""
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinecraftServer
from .const import DOMAIN, ICON_STATUS, KEY_STATUS
from .entity import MinecraftServerEntity


@dataclass
class MinecraftServerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Minecraft Server binary sensor entities."""


STATUS_BINARY_SENSOR_DESCRIPTION = MinecraftServerBinarySensorEntityDescription(
    key=KEY_STATUS,
    translation_key=KEY_STATUS,
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    icon=ICON_STATUS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Minecraft Server binary sensor platform."""
    server = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities list.
    entities = [
        MinecraftServerBinarySensorEntity(server, STATUS_BINARY_SENSOR_DESCRIPTION)
    ]

    # Add binary sensor entities.
    async_add_entities(entities, True)


class MinecraftServerBinarySensorEntity(MinecraftServerEntity, BinarySensorEntity):
    """Representation of a Minecraft Server binary sensor base entity."""

    entity_description: MinecraftServerBinarySensorEntityDescription

    def __init__(
        self,
        server: MinecraftServer,
        description: MinecraftServerBinarySensorEntityDescription,
    ) -> None:
        """Initialize binary sensor base entity."""
        super().__init__(server=server)
        self.entity_description = description
        self._attr_unique_id = f"{server.unique_id}-{description.key}"
        self._attr_is_on = False

    async def async_update(self) -> None:
        """Update binary sensor state."""
        self._attr_is_on = self._server.online
