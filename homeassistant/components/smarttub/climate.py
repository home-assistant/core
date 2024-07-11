"""Platform for climate integration."""

from __future__ import annotations

from typing import Any

from smarttub import Spa

from homeassistant.components.climate import (
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubEntity

PRESET_DAY = "day"
PRESET_READY = "ready"

PRESET_MODES = {
    Spa.HeatMode.AUTO: PRESET_NONE,
    Spa.HeatMode.ECONOMY: PRESET_ECO,
    Spa.HeatMode.DAY: PRESET_DAY,
    Spa.HeatMode.READY: PRESET_READY,
}

HEAT_MODES = {v: k for k, v in PRESET_MODES.items()}

HVAC_ACTIONS = {
    "OFF": HVACAction.IDLE,
    "ON": HVACAction.HEATING,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up climate entity for the thermostat in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = [
        SmartTubThermostat(controller.coordinator, spa) for spa in controller.spas
    ]

    async_add_entities(entities)


class SmartTubThermostat(SmartTubEntity, ClimateEntity):
    """The target water temperature for the spa."""

    # SmartTub devices don't seem to have the option of disabling the heater,
    # so this is always HVACMode.HEAT.
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    # Only target temperature is supported.
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_preset_modes = list(PRESET_MODES.values())
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Thermostat")

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        return HVAC_ACTIONS.get(self.spa_status.heater)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode.

        As with hvac_mode, we don't really have an option here.
        """
        if hvac_mode == HVACMode.HEAT:
            return
        raise NotImplementedError(hvac_mode)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        min_temp = DEFAULT_MIN_TEMP
        return TemperatureConverter.convert(
            min_temp, UnitOfTemperature.CELSIUS, self.temperature_unit
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        max_temp = DEFAULT_MAX_TEMP
        return TemperatureConverter.convert(
            max_temp, UnitOfTemperature.CELSIUS, self.temperature_unit
        )

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        return PRESET_MODES[self.spa_status.heat_mode]

    @property
    def current_temperature(self):
        """Return the current water temperature."""
        return self.spa_status.water.temperature

    @property
    def target_temperature(self):
        """Return the target water temperature."""
        return self.spa_status.set_temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self.spa.set_temperature(temperature)
        await self.coordinator.async_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Activate the specified preset mode."""
        heat_mode = HEAT_MODES[preset_mode]
        await self.spa.set_heat_mode(heat_mode)
        await self.coordinator.async_refresh()
