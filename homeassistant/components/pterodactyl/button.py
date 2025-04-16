"""Button platform for the Pterodactyl integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import (
    PterodactylAuthorizationError,
    PterodactylCommand,
    PterodactylConnectionError,
)
from .coordinator import PterodactylConfigEntry, PterodactylCoordinator
from .entity import PterodactylEntity

KEY_START_SERVER = "start_server"
KEY_STOP_SERVER = "stop_server"
KEY_RESTART_SERVER = "restart_server"
KEY_FORCE_STOP_SERVER = "force_stop_server"

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PterodactylButtonEntityDescription(ButtonEntityDescription):
    """Class describing Pterodactyl button entities."""

    command: PterodactylCommand


BUTTON_DESCRIPTIONS = [
    PterodactylButtonEntityDescription(
        key=KEY_START_SERVER,
        translation_key=KEY_START_SERVER,
        command=PterodactylCommand.START_SERVER,
    ),
    PterodactylButtonEntityDescription(
        key=KEY_STOP_SERVER,
        translation_key=KEY_STOP_SERVER,
        command=PterodactylCommand.STOP_SERVER,
    ),
    PterodactylButtonEntityDescription(
        key=KEY_RESTART_SERVER,
        translation_key=KEY_RESTART_SERVER,
        command=PterodactylCommand.RESTART_SERVER,
    ),
    PterodactylButtonEntityDescription(
        key=KEY_FORCE_STOP_SERVER,
        translation_key=KEY_FORCE_STOP_SERVER,
        command=PterodactylCommand.FORCE_STOP_SERVER,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PterodactylConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pterodactyl button platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        PterodactylButtonEntity(coordinator, identifier, description, config_entry)
        for identifier in coordinator.api.identifiers
        for description in BUTTON_DESCRIPTIONS
    )


class PterodactylButtonEntity(PterodactylEntity, ButtonEntity):
    """Representation of a Pterodactyl button entity."""

    entity_description: PterodactylButtonEntityDescription

    def __init__(
        self,
        coordinator: PterodactylCoordinator,
        identifier: str,
        description: PterodactylButtonEntityDescription,
        config_entry: PterodactylConfigEntry,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, identifier, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.game_server_data.uuid}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.api.async_send_command(
                self.identifier, self.entity_description.command
            )
        except PterodactylConnectionError as err:
            raise HomeAssistantError(
                f"Failed to send action '{self.entity_description.key}': Connection error"
            ) from err
        except PterodactylAuthorizationError as err:
            raise HomeAssistantError(
                f"Failed to send action '{self.entity_description.key}': Unauthorized"
            ) from err
