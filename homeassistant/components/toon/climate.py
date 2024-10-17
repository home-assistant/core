"""Support for Toon thermostat."""

from __future__ import annotations

from typing import Any

from toonapi import (
    ACTIVE_STATE_AWAY,
    ACTIVE_STATE_COMFORT,
    ACTIVE_STATE_HOME,
    ACTIVE_STATE_SLEEP,
)

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_HOME,
    PRESET_SLEEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToonDataUpdateCoordinator
from .const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN
from .entity import ToonDisplayDeviceEntity
from .helpers import toon_exception_handler


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Toon binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ToonThermostatDevice(coordinator)])


class ToonThermostatDevice(ToonDisplayDeviceEntity, ClimateEntity):
    """Representation of a Toon climate device."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_icon = "mdi:thermostat"
    _attr_max_temp = DEFAULT_MAX_TEMP
    _attr_min_temp = DEFAULT_MIN_TEMP
    _attr_name = "Thermostat"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: ToonDataUpdateCoordinator,
    ) -> None:
        """Initialize Toon climate entity."""
        super().__init__(coordinator)
        self._attr_hvac_modes = [HVACMode.HEAT]
        self._attr_preset_modes = [
            PRESET_AWAY,
            PRESET_COMFORT,
            PRESET_HOME,
            PRESET_SLEEP,
        ]
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.data.agreement.agreement_id}_climate"
        )

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        if self.coordinator.data.thermostat.heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        mapping = {
            ACTIVE_STATE_AWAY: PRESET_AWAY,
            ACTIVE_STATE_COMFORT: PRESET_COMFORT,
            ACTIVE_STATE_HOME: PRESET_HOME,
            ACTIVE_STATE_SLEEP: PRESET_SLEEP,
        }
        return mapping.get(self.coordinator.data.thermostat.active_state)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.thermostat.current_display_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.coordinator.data.thermostat.current_setpoint

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the current state of the burner."""
        return {"heating_type": self.coordinator.data.agreement.heating_type}

    @toon_exception_handler
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Change the setpoint of the thermostat."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self.coordinator.toon.set_current_setpoint(temperature)

    @toon_exception_handler
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        mapping = {
            PRESET_AWAY: ACTIVE_STATE_AWAY,
            PRESET_COMFORT: ACTIVE_STATE_COMFORT,
            PRESET_HOME: ACTIVE_STATE_HOME,
            PRESET_SLEEP: ACTIVE_STATE_SLEEP,
        }
        if preset_mode in mapping:
            await self.coordinator.toon.set_active_state(mapping[preset_mode])

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        # Intentionally left empty
        # The HAVC mode is always HEAT
