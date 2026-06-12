"""Sandbox proxy for ``water_heater`` entities."""

from typing import Any

from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_OPERATION_LIST,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    ATTR_TEMPERATURE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxWaterHeaterEntity(SandboxProxyEntity, WaterHeaterEntity):
    """Proxy for a ``water_heater`` entity in a sandbox."""

    _features_flag = WaterHeaterEntityFeature

    @property
    def temperature_unit(self) -> str:
        """Return the unit declared by the sandbox-side entity."""
        return str(
            self.description.capabilities.get(
                "temperature_unit", UnitOfTemperature.CELSIUS
            )
        )

    @property
    def current_operation(self) -> str | None:
        """Return the cached current operation."""
        value = self._state_cache.get("state")
        if value in (None, "unavailable", "unknown"):
            return None
        return value

    @property
    def operation_list(self) -> list[str] | None:
        """Return the configured operation list."""
        value = self.description.capabilities.get(ATTR_OPERATION_LIST)
        return list(value) if value else None

    @property
    def current_temperature(self) -> float | None:
        """Return the cached current temperature."""
        value = self._state_cache.get(ATTR_CURRENT_TEMPERATURE)
        return None if value is None else float(value)

    @property
    def target_temperature(self) -> float | None:
        """Return the cached target temperature."""
        value = self._state_cache.get(ATTR_TEMPERATURE)
        return None if value is None else float(value)

    @property
    def target_temperature_high(self) -> float | None:
        """Return the cached high target temperature."""
        value = self._state_cache.get(ATTR_TARGET_TEMP_HIGH)
        return None if value is None else float(value)

    @property
    def target_temperature_low(self) -> float | None:
        """Return the cached low target temperature."""
        value = self._state_cache.get(ATTR_TARGET_TEMP_LOW)
        return None if value is None else float(value)

    @property
    def target_temperature_step(self) -> float | None:
        """Return the configured target temperature step."""
        value = self.description.capabilities.get(ATTR_TARGET_TEMP_STEP)
        return float(value) if value is not None else None

    @property
    def min_temp(self) -> float:
        """Return the configured minimum temperature."""
        value = self.description.capabilities.get(ATTR_MIN_TEMP)
        return float(value) if value is not None else super().min_temp

    @property
    def max_temp(self) -> float:
        """Return the configured maximum temperature."""
        value = self.description.capabilities.get(ATTR_MAX_TEMP)
        return float(value) if value is not None else super().max_temp

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return the cached away-mode flag."""
        value = self._state_cache.get("away_mode")
        if value is None:
            return None
        return value == "on"

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Forward set_temperature."""
        await self._call_service("set_temperature", **kwargs)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Forward set_operation_mode."""
        await self._call_service("set_operation_mode", operation_mode=operation_mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on."""
        await self._call_service("turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off."""
        await self._call_service("turn_off", **kwargs)

    async def async_turn_away_mode_on(self) -> None:
        """Forward turn_away_mode_on."""
        await self._call_service("turn_away_mode_on")

    async def async_turn_away_mode_off(self) -> None:
        """Forward turn_away_mode_off."""
        await self._call_service("turn_away_mode_off")
