"""Binary sensor platform of the Pterodactyl integration."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PterodactylConfigEntry, PterodactylCoordinator
from .entity import PterodactylEntity

KEY_STATUS = "status"


BINARY_SENSOR_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key=KEY_STATUS,
        translation_key=KEY_STATUS,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
]

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PterodactylConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pterodactyl binary sensor platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        PterodactylBinarySensorEntity(
            coordinator, identifier, description, config_entry
        )
        for identifier in coordinator.api.identifiers
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class PterodactylBinarySensorEntity(PterodactylEntity, BinarySensorEntity):
    """Representation of a Pterodactyl binary sensor base entity."""

    def __init__(
        self,
        coordinator: PterodactylCoordinator,
        identifier: str,
        description: BinarySensorEntityDescription,
        config_entry: PterodactylConfigEntry,
    ) -> None:
        """Initialize binary sensor base entity."""
        super().__init__(coordinator, identifier, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.game_server_data.uuid}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return binary sensor state."""
        return self.game_server_data.state == "running"
