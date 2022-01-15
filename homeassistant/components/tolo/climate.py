"""TOLO Sauna climate controls (main sauna control)."""

from __future__ import annotations

from typing import Any

from tololib.const import Calefaction

from homeassistant.components.climate import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_OFF,
    FAN_ON,
    HVAC_MODE_DRY,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToloSaunaCoordinatorEntity, ToloSaunaUpdateCoordinator
from .const import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_HUMIDITY,
    DEFAULT_MIN_TEMP,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate controls for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SaunaClimate(coordinator, entry)])


class SaunaClimate(ToloSaunaCoordinatorEntity, ClimateEntity):
    """Sauna climate control."""

    _attr_fan_modes = [FAN_ON, FAN_OFF]
    _attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_DRY]
    _attr_max_humidity = DEFAULT_MAX_HUMIDITY
    _attr_max_temp = DEFAULT_MAX_TEMP
    _attr_min_humidity = DEFAULT_MIN_HUMIDITY
    _attr_min_temp = DEFAULT_MIN_TEMP
    _attr_name = "Sauna Climate"
    _attr_precision = PRECISION_WHOLE
    _attr_supported_features = (
        SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_HUMIDITY | SUPPORT_FAN_MODE
    )
    _attr_target_temperature_step = 1
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Sauna Climate entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_climate"

    @property
    def current_temperature(self) -> int:
        """Return current temperature."""
        return self.coordinator.data.status.current_temperature

    @property
    def current_humidity(self) -> int:
        """Return current humidity."""
        return self.coordinator.data.status.current_humidity

    @property
    def target_temperature(self) -> int:
        """Return target temperature."""
        return self.coordinator.data.settings.target_temperature

    @property
    def target_humidity(self) -> int:
        """Return target humidity."""
        return self.coordinator.data.settings.target_humidity

    @property
    def hvac_mode(self) -> str:
        """Get current HVAC mode."""
        if self.coordinator.data.status.power_on:
            return HVAC_MODE_HEAT
        if (
            not self.coordinator.data.status.power_on
            and self.coordinator.data.status.fan_on
        ):
            return HVAC_MODE_DRY
        return HVAC_MODE_OFF

    @property
    def hvac_action(self) -> str | None:
        """Execute HVAC action."""
        if self.coordinator.data.status.calefaction == Calefaction.HEAT:
            return CURRENT_HVAC_HEAT
        if self.coordinator.data.status.calefaction == Calefaction.KEEP:
            return CURRENT_HVAC_IDLE
        if self.coordinator.data.status.calefaction == Calefaction.INACTIVE:
            if self.coordinator.data.status.fan_on:
                return CURRENT_HVAC_DRY
            return CURRENT_HVAC_OFF
        return None

    @property
    def fan_mode(self) -> str:
        """Return current fan mode."""
        if self.coordinator.data.status.fan_on:
            return FAN_ON
        return FAN_OFF

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self._set_power_and_fan(False, False)
        if hvac_mode == HVAC_MODE_HEAT:
            self._set_power_and_fan(True, False)
        if hvac_mode == HVAC_MODE_DRY:
            self._set_power_and_fan(False, True)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        self.coordinator.client.set_fan_on(fan_mode == FAN_ON)

    def set_humidity(self, humidity: float) -> None:
        """Set desired target humidity."""
        self.coordinator.client.set_target_humidity(round(humidity))

    def set_temperature(self, **kwargs: Any) -> None:
        """Set desired target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self.coordinator.client.set_target_temperature(round(temperature))

    def _set_power_and_fan(self, power_on: bool, fan_on: bool) -> None:
        """Shortcut for setting power and fan of TOLO device on one method."""
        self.coordinator.client.set_power_on(power_on)
        self.coordinator.client.set_fan_on(fan_on)
