"""Support for Rituals Perfume Genie numbers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pyrituals import Diffuser

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfArea
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator
from .entity import DiffuserEntity


@dataclass(frozen=True, kw_only=True)
class RitualsSelectEntityDescription(SelectEntityDescription):
    """Class describing Rituals select entities."""

    current_fn: Callable[[Diffuser], str]
    select_fn: Callable[[Diffuser, str], Awaitable[None]]


ENTITY_DESCRIPTIONS = (
    RitualsSelectEntityDescription(
        key="room_size_square_meter",
        translation_key="room_size_square_meter",
        unit_of_measurement=UnitOfArea.SQUARE_METERS,
        entity_category=EntityCategory.CONFIG,
        options=["15", "30", "60", "100"],
        current_fn=lambda diffuser: str(diffuser.room_size_square_meter),
        select_fn=lambda diffuser, value: (
            diffuser.set_room_size_square_meter(int(value))
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser select entities."""
    coordinators: dict[str, RitualsDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        RitualsSelectEntity(coordinator, description)
        for coordinator in coordinators.values()
        for description in ENTITY_DESCRIPTIONS
    )


class RitualsSelectEntity(DiffuserEntity, SelectEntity):
    """Representation of a diffuser select entity."""

    entity_description: RitualsSelectEntityDescription

    def __init__(
        self,
        coordinator: RitualsDataUpdateCoordinator,
        description: RitualsSelectEntityDescription,
    ) -> None:
        """Initialize the diffuser room size select entity."""
        super().__init__(coordinator, description)
        self._attr_entity_registry_enabled_default = (
            self.coordinator.diffuser.has_battery
        )

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self.coordinator.diffuser)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.coordinator.diffuser, option)
