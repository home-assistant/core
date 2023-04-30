"""Support for Rituals Perfume Genie numbers."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator
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
    coordinators: dict[str, RitualsDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        DiffuserPerfumeAmount(coordinator) for coordinator in coordinators.values()
    )


class DiffuserPerfumeAmount(DiffuserEntity, NumberEntity):
    """Representation of a diffuser perfume amount number."""

    _attr_icon = "mdi:gauge"
    _attr_native_max_value = MAX_PERFUME_AMOUNT
    _attr_native_min_value = MIN_PERFUME_AMOUNT

    def __init__(self, coordinator: RitualsDataUpdateCoordinator) -> None:
        """Initialize the diffuser perfume amount number."""
        super().__init__(coordinator, PERFUME_AMOUNT_SUFFIX)

    @property
    def native_value(self) -> int:
        """Return the current perfume amount."""
        return self.coordinator.diffuser.perfume_amount

    async def async_set_native_value(self, value: float) -> None:
        """Set the perfume amount."""
        if not value.is_integer():
            raise ValueError(
                f"Can't set the perfume amount to {value}. Perfume amount must be an"
                " integer."
            )
        await self.coordinator.diffuser.set_perfume_amount(int(value))
