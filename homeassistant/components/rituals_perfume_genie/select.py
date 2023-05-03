"""Support for Rituals Perfume Genie numbers."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import AREA_SQUARE_METERS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator
from .entity import DiffuserEntity

ROOM_SIZE_SUFFIX = " Room Size"


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
        DiffuserRoomSize(coordinator) for coordinator in coordinators.values()
    )


class DiffuserRoomSize(DiffuserEntity, SelectEntity):
    """Representation of a diffuser room size select entity."""

    _attr_icon = "mdi:ruler-square"
    _attr_unit_of_measurement = AREA_SQUARE_METERS
    _attr_options = ["15", "30", "60", "100"]
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RitualsDataUpdateCoordinator) -> None:
        """Initialize the diffuser room size select entity."""
        super().__init__(coordinator, ROOM_SIZE_SUFFIX)
        self._attr_entity_registry_enabled_default = (
            self.coordinator.diffuser.has_battery
        )
        self._attr_unique_id = f"{coordinator.diffuser.hublot}-room_size_square_meter"

    @property
    def current_option(self) -> str:
        """Return the diffuser room size."""
        return str(self.coordinator.diffuser.room_size_square_meter)

    async def async_select_option(self, option: str) -> None:
        """Change the diffuser room size."""
        await self.coordinator.diffuser.set_room_size_square_meter(int(option))
