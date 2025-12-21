"""Number platform for NRGkick."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NRGkickConfigEntry, NRGkickDataUpdateCoordinator, NRGkickEntity

_LOGGER = logging.getLogger(__name__)


PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick number entities based on a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    # Get rated current from device info.
    rated_current = (
        coordinator.data.get("info", {}).get("general", {}).get("rated_current", 32)
    )

    entities: list[NRGkickNumber] = [
        NRGkickNumber(
            coordinator,
            key="current_set",
            unit=UnitOfElectricCurrent.AMPERE,
            min_value=6.0,
            max_value=float(rated_current),
            step=0.1,
            value_path=["control", "current_set"],
            mode=NumberMode.SLIDER,
        ),
        NRGkickNumber(
            coordinator,
            key="energy_limit",
            unit="Wh",
            min_value=0,
            max_value=100000,
            step=100,
            value_path=["control", "energy_limit"],
            mode=NumberMode.BOX,
        ),
        NRGkickNumber(
            coordinator,
            key="phase_count",
            unit=None,
            min_value=1,
            max_value=3,
            step=1,
            value_path=["control", "phase_count"],
            mode=NumberMode.SLIDER,
        ),
    ]

    async_add_entities(entities)


class NRGkickNumber(NRGkickEntity, NumberEntity):
    """Representation of a NRGkick number entity."""

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        *,
        key: str,
        unit: str | None,
        min_value: float,
        max_value: float,
        step: float,
        value_path: list[str],
        mode: NumberMode = NumberMode.BOX,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, key)
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_mode = mode
        self._value_path = value_path
        self._attr_entity_category = entity_category

    @property
    def native_value(self) -> float | None:
        """Return the value of the number entity."""
        data: Any = self.coordinator.data
        for key in self._value_path:
            if data is None:
                return None
            data = data.get(key)
        return float(data) if data is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the number entity."""
        if self._key == "current_set":
            await self.coordinator.async_set_current(value)
        elif self._key == "energy_limit":
            await self.coordinator.async_set_energy_limit(int(value))
        elif self._key == "phase_count":
            await self.coordinator.async_set_phase_count(int(value))
