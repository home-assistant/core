"""Support for WeMo heater devices."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .heater_device import Heater, Mode, Temperature

_LOGGER = logging.getLogger(__name__)

# Map WeMo modes to Home Assistant HVAC modes
WEMO_MODE_TO_HVAC = {
    Mode.Off: HVACMode.OFF,
    Mode.Frostprotect: HVACMode.AUTO,
    Mode.Low: HVACMode.HEAT,
    Mode.High: HVACMode.HEAT,
    Mode.Eco: HVACMode.AUTO,
}

# Default HVAC mode mapping (when no preset is selected)
HVAC_TO_WEMO_MODE = {
    HVACMode.OFF: Mode.Off,
    HVACMode.HEAT: Mode.High,
    HVACMode.AUTO: Mode.Eco,
}

# Preset modes for granular control of all 5 heater modes
PRESET_ECO = "eco"
PRESET_LOW = "low"
PRESET_HIGH = "high"
PRESET_FROST_PROTECT = "frost_protect"

PRESET_TO_WEMO_MODE = {
    PRESET_ECO: Mode.Eco,
    PRESET_LOW: Mode.Low,
    PRESET_HIGH: Mode.High,
    PRESET_FROST_PROTECT: Mode.Frostprotect,
}

WEMO_MODE_TO_PRESET = {
    Mode.Eco: PRESET_ECO,
    Mode.Low: PRESET_LOW,
    Mode.High: PRESET_HIGH,
    Mode.Frostprotect: PRESET_FROST_PROTECT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WeMo heater climate entities."""
    device = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([WemoHeater(device)])


class WemoHeater(ClimateEntity):
    """Representation of a WeMo heater."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_preset_modes = [PRESET_ECO, PRESET_LOW, PRESET_HIGH, PRESET_FROST_PROTECT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.PRESET_MODE
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, device: Heater) -> None:
        """Initialize the WeMo heater."""
        self._device = device
        self._attr_name = device.name
        self._attr_unique_id = device.serial_number
        self._cached_target_temp = None
        self._cache_timestamp = 0
        self._setting_temperature = False  # Flag to prevent cache clearing during set

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        import time
        
        # If we have a cached value that's less than 10 seconds old, use it
        if self._cached_target_temp is not None:
            age = time.time() - self._cache_timestamp
            if age < 10:  # Cache valid for 10 seconds
                return self._cached_target_temp
        
        # Otherwise return device value
        return self._device.target_temperature

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement.
        
        Always return Celsius since the WeMo device operates in Celsius
        and we handle the conversion internally.
        """
        # Always use Celsius - the device operates in Celsius mode
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        return WEMO_MODE_TO_HVAC.get(self._device.mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if self._device.mode == Mode.Off:
            return HVACAction.OFF
        if self._device.heating_status:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        # Return None when in Off mode (no preset)
        if self._device.mode == Mode.Off:
            return None
        # Return the corresponding preset for current mode
        return WEMO_MODE_TO_PRESET.get(self._device.mode, PRESET_ECO)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            return 5.0
        return 41.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            return 35.0
        return 95.0

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 1.0

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        import time
        import asyncio
        
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # Round to whole degree (heater only supports whole degrees)
        temperature = round(temperature)

        # Set flag to prevent cache clearing during this operation
        self._setting_temperature = True
        
        # Cache the requested temperature for immediate UI feedback
        self._cached_target_temp = temperature
        self._cache_timestamp = time.time()
        
        # Immediately update UI with cached value
        self.async_write_ha_state()

        # Send to device in background
        await self.hass.async_add_executor_job(
            self._device.set_target_temperature, temperature
        )
        
        # Keep the flag set for 3 more seconds to prevent updates from clearing cache
        await asyncio.sleep(3)
        self._setting_temperature = False
        
        # Update UI again after device confirms
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode.
        
        When setting HVAC mode without a preset, use default modes:
        - OFF -> Off
        - HEAT -> High
        - AUTO -> Eco
        """
        if hvac_mode not in HVAC_TO_WEMO_MODE:
            _LOGGER.warning("Unsupported HVAC mode: %s", hvac_mode)
            return

        wemo_mode = HVAC_TO_WEMO_MODE[hvac_mode]
        await self.hass.async_add_executor_job(self._device.set_mode, wemo_mode)
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode.
        
        Preset modes provide granular control over all heater modes:
        - eco: Eco mode (energy saving)
        - low: Low heat
        - high: High heat  
        - frost_protect: Frost protection mode
        """
        if preset_mode not in PRESET_TO_WEMO_MODE:
            _LOGGER.warning("Unsupported preset mode: %s", preset_mode)
            return

        wemo_mode = PRESET_TO_WEMO_MODE[preset_mode]
        await self.hass.async_add_executor_job(self._device.set_mode, wemo_mode)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity."""
        await self.hass.async_add_executor_job(self._device.update_attributes)
        
        # Don't clear cache if we're in the middle of setting temperature
        if self._setting_temperature:
            return
            
        # Clear cache after update so we use real device value
        self._cached_target_temp = None
        self._cache_timestamp = 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "heater_mode": self._device.mode_string,
            "auto_off_time": self._device.auto_off_time,
            "time_remaining": self._device.time_remaining,
        }
