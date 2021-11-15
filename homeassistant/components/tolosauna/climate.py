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
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([SaunaClimate(coordinator, entry)])


class SaunaClimate(ToloSaunaCoordinatorEntity, ClimateEntity):
    """Sauna climate control."""

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Sauna Climate entity."""
        super().__init__(coordinator, entry)

        self._attr_fan_modes = [FAN_ON, FAN_OFF]
        self._attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_DRY]
        self._attr_max_humidity = DEFAULT_MAX_HUMIDITY
        self._attr_max_temp = DEFAULT_MAX_TEMP
        self._attr_min_humidity = DEFAULT_MIN_HUMIDITY
        self._attr_min_temp = DEFAULT_MIN_TEMP
        self._attr_name = "Sauna Climate"
        self._attr_precision = PRECISION_WHOLE
        self._attr_supported_features = (
            SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_HUMIDITY | SUPPORT_FAN_MODE
        )
        self._attr_target_temperature_step = 1
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_unique_id = f"{self._config_entry.entry_id}_climate"

    @property
    def current_temperature(self) -> int:
        """Return current temperature."""
        return self.status.current_temperature

    @property
    def current_humidity(self) -> int:
        """Return current humidity."""
        return self.status.current_humidity

    @property
    def target_temperature(self) -> int:
        """Return target temperature."""
        return self.settings.target_temperature

    @property
    def target_humidity(self) -> int:
        """Return target humidity."""
        return self.settings.target_humidity

    @property
    def hvac_mode(self) -> str:
        """Get current HVAC mode."""
        if self.status.power_on:
            return HVAC_MODE_HEAT
        if not self.status.power_on and self.status.fan_on:
            return HVAC_MODE_DRY
        return HVAC_MODE_OFF

    @property
    def hvac_action(self) -> str | None:
        """Execute HVAC action."""
        if self.status.calefaction == Calefaction.HEAT:
            return CURRENT_HVAC_HEAT
        if self.status.calefaction == Calefaction.KEEP:
            return CURRENT_HVAC_IDLE
        if self.status.calefaction == Calefaction.INACTIVE:
            if self.status.fan_on:
                return CURRENT_HVAC_DRY
            return CURRENT_HVAC_OFF
        return None

    @property
    def fan_mode(self) -> str:
        """Return current fan mode."""
        if self.status.fan_on:
            return FAN_ON
        return FAN_OFF

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.hass.async_add_executor_job(
                self._set_power_and_fan, False, False
            )
        if hvac_mode == HVAC_MODE_HEAT:
            await self.hass.async_add_executor_job(self._set_power_and_fan, True, False)
        if hvac_mode == HVAC_MODE_DRY:
            await self.hass.async_add_executor_job(self._set_power_and_fan, False, True)

        await self.coordinator.async_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        if fan_mode == FAN_OFF:
            await self.hass.async_add_executor_job(self.client.set_fan_on, False)
        if fan_mode == FAN_ON:
            await self.hass.async_add_executor_job(self.client.set_fan_on, True)

        await self.coordinator.async_refresh()

    async def async_set_humidity(self, humidity: float) -> None:
        """Set desired target humidity."""
        await self.hass.async_add_executor_job(
            self.client.set_target_humidity, int(humidity)
        )
        await self.coordinator.async_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set desired target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        await self.hass.async_add_executor_job(
            self.client.set_target_temperature, int(temperature)
        )
        await self.coordinator.async_refresh()

    def _set_power_and_fan(self, power_on: bool, fan_on: bool) -> None:
        self.client.set_power_on(power_on)
        self.client.set_fan_on(fan_on)
