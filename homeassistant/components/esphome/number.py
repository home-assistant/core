"""Support for esphome numbers."""
from __future__ import annotations

import math

from aioesphomeapi import (
    EntityInfo,
    NumberInfo,
    NumberMode as EsphomeNumberMode,
    NumberState,
)

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .entity import EsphomeEntity, esphome_state_property, platform_async_setup_entry
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

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        self._attr_device_class = try_parse_enum(
            NumberDeviceClass, self._static_info.device_class
        )
        self._attr_native_min_value = static_info.min_value
        self._attr_native_max_value = static_info.max_value
        self._attr_native_step = static_info.step
        # protobuf doesn't support nullable strings so we need to check
        # if the string is empty
        if unit_of_measurement := static_info.unit_of_measurement:
            self._attr_native_unit_of_measurement = unit_of_measurement
        if mode := static_info.mode:
            self._attr_mode = NUMBER_MODES.from_esphome(mode)
        else:
            self._attr_mode = NumberMode.AUTO

    @property
    @esphome_state_property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        state = self._state
        if state.missing_state or not math.isfinite(state.state):
            return None
        return state.state

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._client.number_command(self._key, value)
