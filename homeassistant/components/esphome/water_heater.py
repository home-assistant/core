"""Support for ESPHome water heaters."""

from __future__ import annotations

from functools import partial
from typing import Any

from aioesphomeapi import EntityInfo, WaterHeaterInfo, WaterHeaterMode, WaterHeaterState

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import callback

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    esphome_float_state_property,
    esphome_state_property,
    platform_async_setup_entry,
)
from .enum_mapper import EsphomeEnumMapper

PARALLEL_UPDATES = 0


_WATER_HEATER_MODES: EsphomeEnumMapper[WaterHeaterMode, str] = EsphomeEnumMapper(
    {
        WaterHeaterMode.OFF: "off",
        WaterHeaterMode.ECO: "eco",
        WaterHeaterMode.ELECTRIC: "electric",
        WaterHeaterMode.PERFORMANCE: "performance",
        WaterHeaterMode.HIGH_DEMAND: "high_demand",
        WaterHeaterMode.HEAT_PUMP: "heat_pump",
        WaterHeaterMode.GAS: "gas",
    }
)


class EsphomeWaterHeater(
    EsphomeEntity[WaterHeaterInfo, WaterHeaterState], WaterHeaterEntity
):
    """A water heater implementation for ESPHome."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_TENTHS

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        self._attr_min_temp = static_info.min_temperature
        self._attr_max_temp = static_info.max_temperature
        features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
        if static_info.supported_modes:
            features |= WaterHeaterEntityFeature.OPERATION_MODE
            self._attr_operation_list = [
                _WATER_HEATER_MODES.from_esphome(mode)
                for mode in static_info.supported_modes
            ]
        else:
            self._attr_operation_list = None
        self._attr_supported_features = features

    @property
    @esphome_float_state_property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._state.current_temperature

    @property
    @esphome_float_state_property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._state.target_temperature

    @property
    @esphome_state_property
    def current_operation(self) -> str | None:
        """Return current operation mode."""
        return _WATER_HEATER_MODES.from_esphome(self._state.mode)

    @convert_api_error_ha_error
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        self._client.water_heater_command(
            key=self._key,
            target_temperature=kwargs[ATTR_TEMPERATURE],
            device_id=self._static_info.device_id,
        )

    @convert_api_error_ha_error
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self._client.water_heater_command(
            key=self._key,
            mode=_WATER_HEATER_MODES.from_hass(operation_mode),
            device_id=self._static_info.device_id,
        )


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=WaterHeaterInfo,
    entity_type=EsphomeWaterHeater,
    state_type=WaterHeaterState,
)
