"""Sandbox proxy for water_heater entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxWaterHeaterEntity(SandboxProxyEntity, WaterHeaterEntity):
    """Proxy for a water_heater entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy water heater entity."""
        super().__init__(description, manager)
        self._attr_supported_features = WaterHeaterEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if operation_list := caps.get("operation_list"):
            self._attr_operation_list = operation_list
        if (min_temp := caps.get("min_temp")) is not None:
            self._attr_min_temp = min_temp
        if (max_temp := caps.get("max_temp")) is not None:
            self._attr_max_temp = max_temp
        if temp_unit := caps.get("temperature_unit"):
            self._attr_temperature_unit = temp_unit

    @property
    def current_operation(self) -> str | None:
        """Return the current operation."""
        return self._state_cache.get("current_operation")

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._state_cache.get("current_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._state_cache.get("target_temperature")

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return if away mode is on."""
        return self._state_cache.get("is_away_mode_on")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Forward set_temperature to sandbox."""
        await self._forward_method("async_set_temperature", **kwargs)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Forward set_operation_mode to sandbox."""
        await self._forward_method("async_set_operation_mode", operation_mode=operation_mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)
