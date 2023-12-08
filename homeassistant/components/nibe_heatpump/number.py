"""The Nibe Heat Pump numbers."""
from __future__ import annotations

from nibe.coil import Coil, CoilData

from homeassistant.components.number import ENTITY_ID_FORMAT, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CoilEntity, Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Number(coordinator, coil)
        for coil in coordinator.coils
        if coil.is_writable and not coil.mappings
    )


def _get_numeric_limits(size: str):
    """Calculate the integer limits of a signed or unsigned integer value."""
    if size[0] == "u":
        return (0, pow(2, int(size[1:])) - 1)
    if size[0] == "s":
        return (-pow(2, int(size[1:]) - 1), pow(2, int(size[1:]) - 1) - 1)
    raise ValueError(f"Invalid size type specified {size}")


class Number(CoilEntity, NumberEntity):
    """Number entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Coordinator, coil: Coil) -> None:
        """Initialize entity."""
        super().__init__(coordinator, coil, ENTITY_ID_FORMAT)
        if coil.min is None or coil.max is None:
            (
                self._attr_native_min_value,
                self._attr_native_max_value,
            ) = _get_numeric_limits(coil.size)
            self._attr_native_min_value /= coil.factor
            self._attr_native_max_value /= coil.factor
        else:
            self._attr_native_min_value = float(coil.min)
            self._attr_native_max_value = float(coil.max)

        self._attr_native_step = 1 / coil.factor
        self._attr_native_unit_of_measurement = coil.unit

    def _async_read_coil(self, data: CoilData) -> None:
        if data.value is None:
            self._attr_native_value = None
            return

        try:
            self._attr_native_value = float(data.value)  # type: ignore[arg-type]
        except ValueError:
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._async_write_coil(value)
