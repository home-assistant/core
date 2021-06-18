"""Support for Rituals Perfume Genie numbers."""
from __future__ import annotations

from pyrituals import Diffuser

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import AREA_SQUARE_METERS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RitualsDataUpdateCoordinator
from .const import ATTRIBUTES, COORDINATORS, DEVICES, DOMAIN, ROOM
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
    entities: list[DiffuserEntity] = []
    for hublot, diffuser in diffusers.items():
        coordinator = coordinators[hublot]
        entities.append(DiffuserRoomSize(diffuser, coordinator))

    async_add_entities(entities)


class DiffuserRoomSize(DiffuserEntity, SelectEntity):
    """Representation of a diffuser room size select entity."""

    def __init__(
        self, diffuser: Diffuser, coordinator: RitualsDataUpdateCoordinator
    ) -> None:
        """Initialize the diffuser room size select entity."""
        super().__init__(diffuser, coordinator, ROOM_SIZE_SUFFIX)
        self._attr_icon = "mdi:ruler-square"
        self._attr_unit_of_measurement = AREA_SQUARE_METERS
        self._attr_options = ["15", "30", "60", "100"]

    @property
    def current_option(self) -> str:
        """Return the diffuser room size."""
        return {
            "1": "15",
            "2": "30",
            "3": "60",
            "4": "100",
        }[self._diffuser.hub_data[ATTRIBUTES][ROOM]]

    async def async_select_option(self, option: str) -> None:
        """Change the diffuser room size."""
        if option in self.options:
            await self._diffuser.set_room_size(
                {
                    "15": 1,
                    "30": 2,
                    "60": 3,
                    "100": 4,
                }[option]
            )
        else:
            raise ValueError(
                f"Can't set the room size to {option}. Allowed room sizes are: {self.options}"
            )
