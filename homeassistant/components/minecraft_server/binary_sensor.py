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

from .const import DOMAIN
from .coordinator import MinecraftServerCoordinator
from .entity import MinecraftServerEntity

ICON_STATUS = "mdi:lan"

KEY_STATUS = "status"


@dataclass(frozen=True)
class MinecraftServerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Minecraft Server binary sensor entities."""


BINARY_SENSOR_DESCRIPTIONS = [
    MinecraftServerBinarySensorEntityDescription(
        key=KEY_STATUS,
        translation_key=KEY_STATUS,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon=ICON_STATUS,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Minecraft Server binary sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add binary sensor entities.
    async_add_entities(
        [
            MinecraftServerBinarySensorEntity(coordinator, description, config_entry)
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )


class MinecraftServerBinarySensorEntity(MinecraftServerEntity, BinarySensorEntity):
    """Representation of a Minecraft Server binary sensor base entity."""

    entity_description: MinecraftServerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MinecraftServerCoordinator,
        description: MinecraftServerBinarySensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize binary sensor base entity."""
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}-{description.key}"
        self._attr_is_on = False

    @property
    def available(self) -> bool:
        """Return binary sensor availability."""
        return True

    @property
    def is_on(self) -> bool:
        """Return binary sensor state."""
        return self.coordinator.last_update_success
