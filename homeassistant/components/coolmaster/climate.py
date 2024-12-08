"""CoolMasterNet platform to control of CoolMasterNet Climate Devices."""

from __future__ import annotations

import logging
from typing import Any

from pycoolmasternet_async import SWING_MODES

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SUPPORTED_MODES, DATA_COORDINATOR, DATA_INFO, DOMAIN
from .entity import CoolmasterEntity

CM_TO_HA_STATE = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "auto": HVACMode.HEAT_COOL,
    "dry": HVACMode.DRY,
    "fan": HVACMode.FAN_ONLY,
}

HA_STATE_TO_CM = {value: key for key, value in CM_TO_HA_STATE.items()}

FAN_MODES = ["low", "med", "high", "auto"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CoolMasterNet climate platform."""
    info = hass.data[DOMAIN][config_entry.entry_id][DATA_INFO]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    supported_modes = config_entry.data.get(CONF_SUPPORTED_MODES)
    async_add_entities(
        CoolmasterClimate(coordinator, unit_id, info, supported_modes)
        for unit_id in coordinator.data
    )


class CoolmasterClimate(CoolmasterEntity, ClimateEntity):
    """Representation of a coolmaster climate device."""

    _attr_name = None

    def __init__(self, coordinator, unit_id, info, supported_modes):
        """Initialize the climate device."""
        super().__init__(coordinator, unit_id, info)
        self._attr_hvac_modes = supported_modes
        self._attr_unique_id = unit_id

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        if self.swing_mode:
            supported_features |= ClimateEntityFeature.SWING_MODE
        return supported_features

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self._unit.temperature_unit == "celsius":
            return UnitOfTemperature.CELSIUS

        return UnitOfTemperature.FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._unit.temperature

    @property
    def target_temperature(self):
        """Return the temperature we are trying to reach."""
        return self._unit.thermostat

    @property
    def hvac_mode(self):
        """Return hvac target hvac state."""
        mode = self._unit.mode
        if not self._unit.is_on:
            return HVACMode.OFF

        return CM_TO_HA_STATE[mode]

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._unit.fan_speed

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return FAN_MODES

    @property
    def swing_mode(self) -> str | None:
        """Return the swing mode setting."""
        return self._unit.swing

    @property
    def swing_modes(self) -> list[str] | None:
        """Return swing modes if supported."""
        return SWING_MODES if self.swing_mode is not None else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.debug("Setting temp of %s to %s", self.unique_id, str(temp))
            self._unit = await self._unit.set_thermostat(temp)
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        _LOGGER.debug("Setting fan mode of %s to %s", self.unique_id, fan_mode)
        self._unit = await self._unit.set_fan_speed(fan_mode)
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        _LOGGER.debug("Setting swing mode of %s to %s", self.unique_id, swing_mode)
        try:
            self._unit = await self._unit.set_swing(swing_mode)
        except ValueError as error:
            raise HomeAssistantError(error) from error
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode of %s to %s", self.unique_id, hvac_mode)

        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            self._unit = await self._unit.set_mode(HA_STATE_TO_CM[hvac_mode])
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        """Turn on."""
        _LOGGER.debug("Turning %s on", self.unique_id)
        self._unit = await self._unit.turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off."""
        _LOGGER.debug("Turning %s off", self.unique_id)
        self._unit = await self._unit.turn_off()
        self.async_write_ha_state()
