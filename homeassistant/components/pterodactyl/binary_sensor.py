"""Binary sensor platform of the Pterodactyl integration."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
        [
            PterodactylBinarySensorEntity(
                coordinator, identifier, description, config_entry
            )
            for identifier in coordinator.api.identifiers
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
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
        self.identifier = identifier
        self._attr_unique_id = f"{config_entry.entry_id}-{identifier}-{description.key}"
        self._attr_is_on = False

    @property
    def available(self) -> bool:
        """Return binary sensor availability."""
        return True

    @property
    def is_on(self) -> bool:
        """Return binary sensor state."""
        index = self.coordinator.api.get_index_from_identifier(self.identifier)

        if index is None:
            raise HomeAssistantError(
                f"Identifier '{self.identifier}' not found in data list"
            )

        return self.coordinator.data[index].state == "running"
