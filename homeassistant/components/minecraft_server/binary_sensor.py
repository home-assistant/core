"""The Minecraft Server binary sensor platform."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MinecraftServerConfigEntry, MinecraftServerCoordinator
from .entity import MinecraftServerEntity

KEY_STATUS = "status"


BINARY_SENSOR_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key=KEY_STATUS,
        translation_key=KEY_STATUS,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
]

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MinecraftServerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Minecraft Server binary sensor platform."""
    coordinator = config_entry.runtime_data

    # Add binary sensor entities.
    async_add_entities(
        [
            MinecraftServerBinarySensorEntity(coordinator, description, config_entry)
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )


class MinecraftServerBinarySensorEntity(MinecraftServerEntity, BinarySensorEntity):
    """Representation of a Minecraft Server binary sensor base entity."""

    def __init__(
        self,
        coordinator: MinecraftServerCoordinator,
        description: BinarySensorEntityDescription,
        config_entry: MinecraftServerConfigEntry,
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
