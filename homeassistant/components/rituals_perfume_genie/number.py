"""Support for Rituals Perfume Genie numbers."""
from __future__ import annotations

from pyrituals import Diffuser

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RitualsDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import DiffuserEntity

MIN_PERFUME_AMOUNT = 1
MAX_PERFUME_AMOUNT = 3

PERFUME_AMOUNT_SUFFIX = " Perfume Amount"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser numbers."""
    diffusers = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities: list[DiffuserEntity] = []
    for hublot, diffuser in diffusers.items():
        coordinator = coordinators[hublot]
        entities.append(DiffuserPerfumeAmount(diffuser, coordinator))

    async_add_entities(entities)


class DiffuserPerfumeAmount(DiffuserEntity, NumberEntity):
    """Representation of a diffuser perfume amount number."""

    _attr_icon = "mdi:gauge"
    _attr_native_max_value = MAX_PERFUME_AMOUNT
    _attr_native_min_value = MIN_PERFUME_AMOUNT

    def __init__(
        self, diffuser: Diffuser, coordinator: RitualsDataUpdateCoordinator
    ) -> None:
        """Initialize the diffuser perfume amount number."""
        super().__init__(diffuser, coordinator, PERFUME_AMOUNT_SUFFIX)

    @property
    def native_value(self) -> int:
        """Return the current perfume amount."""
        return self._diffuser.perfume_amount

    async def async_set_native_value(self, value: float) -> None:
        """Set the perfume amount."""
        if not value.is_integer():
            raise ValueError(
                f"Can't set the perfume amount to {value}. Perfume amount must be an integer."
            )
        await self._diffuser.set_perfume_amount(int(value))
