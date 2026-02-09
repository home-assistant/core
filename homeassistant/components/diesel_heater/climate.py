"""Climate platform for Vevor Diesel Heater."""
from __future__ import annotations

PARALLEL_UPDATES = 1

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_NONE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from . import VevorHeaterConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_PRESET_AWAY_TEMP,
    CONF_PRESET_COMFORT_TEMP,
    DEFAULT_PRESET_AWAY_TEMP,
    DEFAULT_PRESET_COMFORT_TEMP,
    DOMAIN,
    RUNNING_STEP_STANDBY,
    RUNNING_STEP_SELF_TEST,
    RUNNING_STEP_IGNITION,
    RUNNING_STEP_RUNNING,
    RUNNING_STEP_COOLDOWN,
    RUNNING_STEP_VENTILATION,
)
from .coordinator import VevorHeaterCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VevorHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vevor Heater climate from config entry."""
    coordinator = entry.runtime_data
    async_add_entities([VevorHeaterClimate(coordinator, entry)])


class VevorHeaterClimate(CoordinatorEntity[VevorHeaterCoordinator], ClimateEntity):
    """Climate entity for Vevor Heater."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_min_temp = 8
    _attr_max_temp = 36
    _attr_target_temperature_step = 1
    _attr_preset_modes = [PRESET_NONE, PRESET_AWAY, PRESET_COMFORT]

    def __init__(self, coordinator: VevorHeaterCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._current_preset: str | None = None
        self._user_cleared_preset: bool = False  # Track if user explicitly selected "None"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }
        self._attr_unique_id = f"{coordinator.address}_climate"

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature (interior/cabin temperature)."""
        return self.coordinator.data.get("cab_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.coordinator.data.get("set_temp")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        running_state = self.coordinator.data.get("running_state", 0)
        if running_state == 1:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action (what the heater is actually doing).

        Uses both running_state and running_step to determine the action:
        - running_state OFF + Standby = OFF (heater is completely off)
        - running_state ON + Standby = IDLE (heater is on but waiting, e.g. Auto Start/Stop)
        """
        running_step = self.coordinator.data.get("running_step")
        running_state = self.coordinator.data.get("running_state", 0)

        if running_step is None:
            return None

        if running_step == RUNNING_STEP_STANDBY:
            # Check if heater is actually ON or OFF
            # When ON but Standby, it's idle (e.g., Auto Start/Stop waiting)
            # When OFF and Standby, it's truly off
            if running_state == 1:  # RUNNING_STATE_ON
                return HVACAction.IDLE
            return HVACAction.OFF
        elif running_step in (RUNNING_STEP_SELF_TEST, RUNNING_STEP_IGNITION, RUNNING_STEP_RUNNING):
            return HVACAction.HEATING
        elif running_step in (RUNNING_STEP_COOLDOWN, RUNNING_STEP_VENTILATION):
            # Cooldown and Ventilation both run fans at full speed
            return HVACAction.FAN
        else:
            # Unknown step, return idle as safe default
            return HVACAction.IDLE

    def _get_away_temp(self) -> int:
        """Get configured away preset temperature."""
        return self._config_entry.data.get(
            CONF_PRESET_AWAY_TEMP, DEFAULT_PRESET_AWAY_TEMP
        )

    def _get_comfort_temp(self) -> int:
        """Get configured comfort preset temperature."""
        return self._config_entry.data.get(
            CONF_PRESET_COMFORT_TEMP, DEFAULT_PRESET_COMFORT_TEMP
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode.

        Auto-detects preset based on current target temperature,
        unless user explicitly cleared the preset.
        """
        # If user explicitly selected "None", respect that choice
        if self._user_cleared_preset:
            return PRESET_NONE

        current_temp = self.coordinator.data.get("set_temp")
        if current_temp is None:
            return self._current_preset if self._current_preset else PRESET_NONE

        # Check if current temp matches a preset
        if current_temp == self._get_away_temp():
            return PRESET_AWAY
        elif current_temp == self._get_comfort_temp():
            return PRESET_COMFORT

        # If we manually set the preset, keep it even if temp doesn't match exactly
        # This handles cases where heater rounds temperature
        return self._current_preset if self._current_preset else PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._current_preset = preset_mode

        if preset_mode == PRESET_AWAY:
            self._user_cleared_preset = False  # Clear the "None" flag
            temp = self._get_away_temp()
            _LOGGER.info("Setting preset to Away (%d°C)", temp)
            await self.coordinator.async_set_temperature(temp)
        elif preset_mode == PRESET_COMFORT:
            self._user_cleared_preset = False  # Clear the "None" flag
            temp = self._get_comfort_temp()
            _LOGGER.info("Setting preset to Comfort (%d°C)", temp)
            await self.coordinator.async_set_temperature(temp)
        elif preset_mode == PRESET_NONE:
            _LOGGER.info("Clearing preset mode")
            # Keep current temperature, just clear the preset
            self._current_preset = None
            self._user_cleared_preset = True  # User explicitly selected "None"
            # Persist the state change
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        temperature = int(temperature)

        # User is manually setting temperature, clear the "None" flag
        self._user_cleared_preset = False

        # Auto-select preset if temperature matches
        if temperature == self._get_away_temp():
            self._current_preset = PRESET_AWAY
        elif temperature == self._get_comfort_temp():
            self._current_preset = PRESET_COMFORT
        else:
            self._current_preset = None

        _LOGGER.info("Setting target temperature to %d°C", temperature)
        await self.coordinator.async_set_temperature(temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            _LOGGER.info("Turning heater ON")
            await self.coordinator.async_turn_on()
        elif hvac_mode == HVACMode.OFF:
            _LOGGER.info("Turning heater OFF")
            await self.coordinator.async_turn_off()

    async def async_turn_on(self) -> None:
        """Turn on the heater."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn off the heater."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
