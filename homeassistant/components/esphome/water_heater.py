"""Support for ESPHome water heaters."""

from __future__ import annotations

from typing import Any, cast

from aioesphomeapi import WaterHeaterInfo, WaterHeaterMode, WaterHeaterState

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import EsphomeEntity, EsphomeEnumMapper, platform_async_setup_entry
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPHome water heaters based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=WaterHeaterInfo,
        entity_type=EsphomeWaterHeater,
        state_type=WaterHeaterState,
    )


class EsphomeWaterHeater(
    EsphomeEntity[WaterHeaterInfo, WaterHeaterState], WaterHeaterEntity
):
    """A water heater implementation for ESPHome."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_TENTHS

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        entity_info: WaterHeaterInfo,
        state_type: type[WaterHeaterState],
    ) -> None:
        """Initialize the water heater."""
        super().__init__(entry_data, entity_info, state_type)

        mode = cast(Any, WaterHeaterMode)
        self._mode_selector = EsphomeEnumMapper(
            {
                mode.OFF: "off",
                mode.ECO: "eco",
                mode.ELECTRIC: "electric",
                mode.PERFORMANCE: "performance",
                mode.HIGH_DEMAND: "high_demand",
                mode.HEAT_PUMP: "heat_pump",
                mode.GAS: "gas",
            }
        )

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
        if self._static_info.supported_modes:
            features |= WaterHeaterEntityFeature.OPERATION_MODE
        return features

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._static_info.min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._static_info.max_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._state.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._state.target_temperature

    @property
    def current_operation(self) -> str | None:
        """Return current operation mode."""
        return self._mode_selector.from_esphome(self._state.mode)

    @property
    def operation_list(self) -> list[str] | None:
        """Return the list of available operation modes."""
        if not self._static_info.supported_modes:
            return None
        return [
            self._mode_selector.from_esphome(mode)
            for mode in self._static_info.supported_modes
        ]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        self._client.water_heater_command(
            key=self._key,
            target_temperature=kwargs[ATTR_TEMPERATURE],
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self._client.water_heater_command(
            key=self._key,
            mode=self._mode_selector.from_hass(operation_mode),
        )
