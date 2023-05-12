"""Support for Balboa Spa Wifi adaptor."""
from __future__ import annotations

from enum import IntEnum
from typing import Any

from pybalboa import SpaClient, SpaControl
from pybalboa.enums import HeatMode, HeatState, TemperatureUnit

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BalboaEntity

HEAT_HVAC_MODE_MAP: dict[IntEnum, HVACMode] = {
    HeatMode.READY: HVACMode.HEAT,
    HeatMode.REST: HVACMode.OFF,
    HeatMode.READY_IN_REST: HVACMode.AUTO,
}
HVAC_HEAT_MODE_MAP = {value: key for key, value in HEAT_HVAC_MODE_MAP.items()}
HEAT_STATE_HVAC_ACTION_MAP = {
    HeatState.OFF: HVACAction.OFF,
    HeatState.HEATING: HVACAction.HEATING,
    HeatState.HEAT_WAITING: HVACAction.IDLE,
}
TEMPERATURE_UNIT_MAP = {
    TemperatureUnit.CELSIUS: UnitOfTemperature.CELSIUS,
    TemperatureUnit.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa climate entity."""
    async_add_entities([BalboaClimateEntity(hass.data[DOMAIN][entry.entry_id])])


class BalboaClimateEntity(BalboaEntity, ClimateEntity):
    """Representation of a Balboa spa climate entity."""

    _attr_icon = "mdi:hot-tub"
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_translation_key = DOMAIN

    def __init__(self, client: SpaClient) -> None:
        """Initialize the climate entity."""
        super().__init__(client, "Climate")
        self._attr_preset_modes = [opt.name.lower() for opt in client.heat_mode.options]

        self._blower: SpaControl | None = None
        if client.blowers and (blower := client.blowers[0]) is not None:
            self._blower = blower
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._fan_mode_map = {opt.name.lower(): opt for opt in blower.options}
            self._attr_fan_modes = list(self._fan_mode_map)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        return HEAT_HVAC_MODE_MAP.get(self._client.heat_mode.state)

    @property
    def hvac_action(self) -> str:
        """Return the current operation mode."""
        return HEAT_STATE_HVAC_ACTION_MAP[self._client.heat_state]

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if (blower := self._blower) is not None:
            return blower.state.name.lower()
        return None

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS:
            return PRECISION_HALVES
        return PRECISION_WHOLE

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMPERATURE_UNIT_MAP[self._client.temperature_unit]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._client.temperature

    @property
    def target_temperature(self) -> float:
        """Return the target temperature we try to reach."""
        return self._client.target_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature supported by the spa."""
        return self._client.temperature_minimum

    @property
    def max_temp(self) -> float:
        """Return the minimum temperature supported by the spa."""
        return self._client.temperature_maximum

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        return self._client.heat_mode.state.name.lower()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        await self._client.set_temperature(kwargs[ATTR_TEMPERATURE])

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._client.heat_mode.set_state(HeatMode[preset_mode.upper()])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if (blower := self._blower) is not None:
            await blower.set_state(self._fan_mode_map[fan_mode])

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._client.heat_mode.set_state(HVAC_HEAT_MODE_MAP[hvac_mode])
