"""Support for Rituals Perfume Genie numbers."""
from __future__ import annotations

from pyrituals import Diffuser

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import AREA_SQUARE_METERS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RitualsDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import DiffuserEntity

ROOM_SIZE_SUFFIX = " Room Size"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser select entities."""
    diffusers = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    async_add_entities(
        DiffuserRoomSize(diffuser, coordinators[hublot])
        for hublot, diffuser in diffusers.items()
    )


class DiffuserRoomSize(DiffuserEntity, SelectEntity):
    """Representation of a diffuser room size select entity."""

    _attr_icon = "mdi:ruler-square"
    _attr_unit_of_measurement = AREA_SQUARE_METERS
    _attr_options = ["15", "30", "60", "100"]
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, diffuser: Diffuser, coordinator: RitualsDataUpdateCoordinator
    ) -> None:
        """Initialize the diffuser room size select entity."""
        super().__init__(diffuser, coordinator, ROOM_SIZE_SUFFIX)
        self._attr_entity_registry_enabled_default = diffuser.has_battery

    @property
    def current_option(self) -> str:
        """Return the diffuser room size."""
        return str(self._diffuser.room_size_square_meter)

    async def async_select_option(self, option: str) -> None:
        """Change the diffuser room size."""
        await self._diffuser.set_room_size_square_meter(int(option))
