"""Binary sensor platform of the Pterodactyl integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import PterodactylGameServer, PterodactylGameServerData
from .coordinator import PterodactylConfigEntry, PterodactylCoordinator
from .entity import PterodactylEntity

KEY_STATUS = "status"
KEY_SUSPENDED = "suspended"


@dataclass(frozen=True, kw_only=True)
class PterodactylBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Pterodactyl binary sensor entities."""

    value_fn: Callable[[PterodactylGameServer, PterodactylGameServerData], bool]


BINARY_SENSOR_DESCRIPTIONS = [
    PterodactylBinarySensorEntityDescription(
        key=KEY_STATUS,
        translation_key=KEY_STATUS,
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda game_server, game_server_data: (
            game_server_data.state == "running"
        ),
    ),
    PterodactylBinarySensorEntityDescription(
        key=KEY_SUSPENDED,
        translation_key=KEY_SUSPENDED,
        value_fn=lambda game_server, game_server_data: game_server.is_suspended,
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
            coordinator, game_server, description, config_entry
        )
        for game_server in coordinator.api.game_servers
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class PterodactylBinarySensorEntity(PterodactylEntity, BinarySensorEntity):
    """Representation of a Pterodactyl binary sensor base entity."""

    def __init__(
        self,
        coordinator: PterodactylCoordinator,
        game_server: PterodactylGameServer,
        description: PterodactylBinarySensorEntityDescription,
        config_entry: PterodactylConfigEntry,
    ) -> None:
        """Initialize binary sensor base entity."""
        super().__init__(coordinator, game_server, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.game_server_data.uuid}_{description.key}"

    entity_description: PterodactylBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return binary sensor state."""
        return self.entity_description.value_fn(self.game_server, self.game_server_data)
