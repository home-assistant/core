"""Select platform for the jvc_projector integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from jvcprojector.projector import JvcProjector, const

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity


@dataclass(frozen=True, kw_only=True)
class JvcProjectorSelectDescription(SelectEntityDescription):
    """Describes JVC Projector select entities."""

    command: Callable[[JvcProjector, str], Awaitable[None]]


# these options correspond to a command and its possible values
# note low latency is intentionally excluded because you can't just turn it on you need to meet conditions first so you should instead switch picture modes
OPTIONS: Final[dict[str, list[str]]] = {
    "input": const.VAL_FUNCTION_INPUT,
    "eshift": const.VAL_TOGGLE,
    "installation_mode": const.VAL_INSTALLATION_MODE,
    "anamorphic": const.VAL_ANAMORPHIC,
    "laser_power": const.VAL_LASER_POWER,
    "laser_dimming": const.VAL_LASER_DIMMING,
}


# type safe command function for a select
def create_select_command(key: str) -> Callable[[JvcProjector, str], Awaitable[None]]:
    """Create a command function for a select."""

    async def command(device: JvcProjector, option: str) -> None:
        await device.send_command(key, option)

    return command


# create a select for each option defined
SELECTS: Final[list[JvcProjectorSelectDescription]] = [
    JvcProjectorSelectDescription(
        key=key,
        translation_key=key,
        options=list(options),
        command=create_select_command(key),
    )
    for key, options in OPTIONS.items()
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JVCConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
        return self.coordinator.data.get(self.entity_description.key)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.command(self.coordinator.device, option)
