"""Platform for eQ-3 climate entities."""

import logging
from typing import Any

from eq3btsmart.const import EQ3_OFF_TEMP, EQ3_ON_TEMP, Eq3OperationMode, Eq3Preset
from eq3btsmart.exceptions import Eq3Exception

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EQ_TO_HA_HVAC, HA_TO_EQ_HVAC, Preset
from .coordinator import Eq3ConfigEntry
from .entity import Eq3Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eq3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Handle config entry setup."""
    async_add_entities(
        [Eq3Climate(entry)],
    )


class Eq3Climate(Eq3Entity, ClimateEntity):
    """Climate entity to represent a eQ-3 thermostat."""

    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = EQ3_OFF_TEMP
    _attr_max_temp = EQ3_ON_TEMP
    _attr_precision = PRECISION_HALVES
    _attr_hvac_modes = list(HA_TO_EQ_HVAC.keys())
    _attr_preset_modes = list(Preset)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.coordinator.data.target_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current hvac mode."""
        return EQ_TO_HA_HVAC[self.coordinator.data.operation_mode]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current hvac action."""
        if self.coordinator.data.operation_mode is Eq3OperationMode.OFF:
            return HVACAction.OFF
        if self.coordinator.data.valve == 0:
            return HVACAction.IDLE
        return HVACAction.HEATING

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        status = self.coordinator.data
        if status.presets is None:
            return PRESET_NONE
        if status.target_temperature == status.presets.eco_temperature:
            return Preset.ECO
        if status.target_temperature == status.presets.comfort_temperature:
            return Preset.COMFORT
        return PRESET_NONE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_HVAC_MODE in kwargs:
            mode: HVACMode | None
            if (mode := kwargs.get(ATTR_HVAC_MODE)) is None:
                return

            if mode is not HVACMode.OFF:
                await self.async_set_hvac_mode(mode)
            else:
                raise ServiceValidationError(
                    f"[{self._mac_address}] Can't change HVAC mode to off while changing temperature",
                )

        temperature: float | None
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        try:
            await self._thermostat.async_set_temperature(temperature)
        except Eq3Exception as ex:
            raise HomeAssistantError(
                f"[{self._mac_address}] Failed setting temperature"
            ) from ex
        except ValueError as ex:
            raise ServiceValidationError("Invalid temperature") from ex

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode is HVACMode.OFF:
            await self.async_set_temperature(temperature=EQ3_OFF_TEMP)

        try:
            await self._thermostat.async_set_mode(HA_TO_EQ_HVAC[hvac_mode])
        except Eq3Exception as ex:
            raise HomeAssistantError(
                f"[{self._mac_address}] Failed setting HVAC mode"
            ) from ex

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        try:
            if preset_mode is Preset.ECO:
                await self._thermostat.async_set_preset(Eq3Preset.ECO)
            elif preset_mode is Preset.COMFORT:
                await self._thermostat.async_set_preset(Eq3Preset.COMFORT)
        except Eq3Exception as ex:
            raise HomeAssistantError(
                f"[{self._mac_address}] Failed setting preset mode"
            ) from ex
