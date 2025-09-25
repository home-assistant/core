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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Eq3ConfigEntry
from .const import EQ_TO_HA_HVAC, HA_TO_EQ_HVAC, Preset
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
    _attr_hvac_mode: HVACMode | None = None
    _attr_hvac_action: HVACAction | None = None
    _attr_preset_mode: str | None = None
    _target_temperature: float | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._target_temperature = self.coordinator.data.target_temperature
        self._attr_hvac_mode = EQ_TO_HA_HVAC[self.coordinator.data.operation_mode]
        self._attr_target_temperature = self._get_target_temperature()
        self._attr_preset_mode = self._get_current_preset_mode()
        self._attr_hvac_action = self._get_current_hvac_action()

        super()._handle_coordinator_update()

    def _get_target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._thermostat.status.target_temperature

    def _get_current_preset_mode(self) -> str:
        """Return the current preset mode."""
        status = self._thermostat.status
        if status.presets is None:
            return PRESET_NONE
        if status.target_temperature == status.presets.eco_temperature:
            return Preset.ECO
        if status.target_temperature == status.presets.comfort_temperature:
            return Preset.COMFORT

        return PRESET_NONE

    def _get_current_hvac_action(self) -> HVACAction:
        """Return the current hvac action."""
        if self._thermostat.status.operation_mode is Eq3OperationMode.OFF:
            return HVACAction.OFF
        if self._thermostat.status.valve == 0:
            return HVACAction.IDLE
        return HVACAction.HEATING

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

        previous_temperature = self._target_temperature
        self._target_temperature = temperature

        self.async_write_ha_state()

        try:
            await self._thermostat.async_set_temperature(temperature)
        except Eq3Exception as ex:
            _LOGGER.error("[%s] Failed setting temperature: %s", self._mac_address, ex)
            self._target_temperature = previous_temperature
            self.async_write_ha_state()
        except ValueError as ex:
            raise ServiceValidationError("Invalid temperature") from ex

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode is HVACMode.OFF:
            await self.async_set_temperature(temperature=EQ3_OFF_TEMP)

        try:
            await self._thermostat.async_set_mode(HA_TO_EQ_HVAC[hvac_mode])
        except Eq3Exception as ex:
            _LOGGER.error("[%s] Failed setting HVAC mode: %s", self._mac_address, ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        match preset_mode:
            case Preset.ECO:
                await self._thermostat.async_set_preset(Eq3Preset.ECO)
            case Preset.COMFORT:
                await self._thermostat.async_set_preset(Eq3Preset.COMFORT)
