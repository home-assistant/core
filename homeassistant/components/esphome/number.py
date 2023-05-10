"""Support for esphome numbers."""
from __future__ import annotations

import math

from aioesphomeapi import NumberInfo, NumberMode as EsphomeNumberMode, NumberState

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry
from .enum_mapper import EsphomeEnumMapper


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up esphome numbers based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="number",
        info_type=NumberInfo,
        entity_type=EsphomeNumber,
        state_type=NumberState,
    )


NUMBER_MODES: EsphomeEnumMapper[EsphomeNumberMode, NumberMode] = EsphomeEnumMapper(
    {
        EsphomeNumberMode.AUTO: NumberMode.AUTO,
        EsphomeNumberMode.BOX: NumberMode.BOX,
        EsphomeNumberMode.SLIDER: NumberMode.SLIDER,
    }
)


class EsphomeNumber(EsphomeEntity[NumberInfo, NumberState], NumberEntity):
    """A number implementation for esphome."""

    @property
    def device_class(self) -> NumberDeviceClass | None:
        """Return the class of this entity."""
        return try_parse_enum(NumberDeviceClass, self._static_info.device_class)

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return super()._static_info.min_value

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return super()._static_info.max_value

    @property
    def native_step(self) -> float:
        """Return the increment/decrement step."""
        return super()._static_info.step

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return super()._static_info.unit_of_measurement

    @property
    def mode(self) -> NumberMode:
        """Return the mode of the entity."""
        if self._static_info.mode:
            return NUMBER_MODES.from_esphome(self._static_info.mode)
        return NumberMode.AUTO

    @property
    @esphome_state_property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        if math.isnan(self._state.state):
            return None
        if self._state.missing_state:
            return None
        return self._state.state

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._client.number_command(self._static_info.key, value)
