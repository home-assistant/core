"""Select platform for the jvc_projector integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from jvcprojector import JvcProjector, const

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity


@dataclass(frozen=True, kw_only=True)
class JvcProjectorSelectDescription(SelectEntityDescription):
    """Describes JVC Projector select entities."""

    command: Callable[[JvcProjector, str], Awaitable[None]]


OPTIONS: Final[dict[str, dict[str, str]]] = {
    "input": {const.HDMI1: const.REMOTE_HDMI_1, const.HDMI2: const.REMOTE_HDMI_2}
}

SELECTS: Final[list[JvcProjectorSelectDescription]] = [
    JvcProjectorSelectDescription(
        key="input",
        translation_key="input",
        options=list(OPTIONS["input"]),
        command=lambda device, option: device.remote(OPTIONS["input"][option]),
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JVCConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        JvcProjectorSelectEntity(coordinator, description) for description in SELECTS
    )


class JvcProjectorSelectEntity(JvcProjectorEntity, SelectEntity):
    """Representation of a JVC Projector select entity."""

    entity_description: JvcProjectorSelectDescription

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        description: JvcProjectorSelectDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.coordinator.data[self.entity_description.key]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.command(self.coordinator.device, option)
