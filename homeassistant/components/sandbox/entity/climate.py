"""Sandbox proxy for climate entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxClimateEntity(SandboxProxyEntity, ClimateEntity):
    """Proxy for a climate entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy climate entity."""
        super().__init__(description, manager)
        self._attr_supported_features = ClimateEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if hvac_modes := caps.get("hvac_modes"):
            self._attr_hvac_modes = [HVACMode(m) for m in hvac_modes]
        if fan_modes := caps.get("fan_modes"):
            self._attr_fan_modes = fan_modes
        if preset_modes := caps.get("preset_modes"):
            self._attr_preset_modes = preset_modes
        if swing_modes := caps.get("swing_modes"):
            self._attr_swing_modes = swing_modes
        if (min_temp := caps.get("min_temp")) is not None:
            self._attr_min_temp = min_temp
        if (max_temp := caps.get("max_temp")) is not None:
            self._attr_max_temp = max_temp
        if (min_humidity := caps.get("min_humidity")) is not None:
            self._attr_min_humidity = min_humidity
        if (max_humidity := caps.get("max_humidity")) is not None:
            self._attr_max_humidity = max_humidity
        if (temp_step := caps.get("target_temperature_step")) is not None:
            self._attr_target_temperature_step = temp_step
        if temp_unit := caps.get("temperature_unit"):
            self._attr_temperature_unit = temp_unit

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        mode = self._state_cache.get("hvac_mode")
        if mode is None:
            return None
        return HVACMode(mode)

    @property
    def hvac_action(self) -> str | None:
        """Return the current HVAC action."""
        return self._state_cache.get("hvac_action")

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._state_cache.get("current_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._state_cache.get("target_temperature")

    @property
    def target_temperature_high(self) -> float | None:
        """Return the high target temperature."""
        return self._state_cache.get("target_temperature_high")

    @property
    def target_temperature_low(self) -> float | None:
        """Return the low target temperature."""
        return self._state_cache.get("target_temperature_low")

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._state_cache.get("current_humidity")

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity."""
        return self._state_cache.get("target_humidity")

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return self._state_cache.get("fan_mode")

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._state_cache.get("preset_mode")

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return self._state_cache.get("swing_mode")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Forward set_temperature to sandbox."""
        await self._forward_method("async_set_temperature", **kwargs)

    async def async_set_humidity(self, humidity: int) -> None:
        """Forward set_humidity to sandbox."""
        await self._forward_method("async_set_humidity", humidity=humidity)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Forward set_fan_mode to sandbox."""
        await self._forward_method("async_set_fan_mode", fan_mode=fan_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Forward set_hvac_mode to sandbox."""
        await self._forward_method("async_set_hvac_mode", hvac_mode=hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Forward set_preset_mode to sandbox."""
        await self._forward_method("async_set_preset_mode", preset_mode=preset_mode)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Forward set_swing_mode to sandbox."""
        await self._forward_method("async_set_swing_mode", swing_mode=swing_mode)

    async def async_turn_on(self) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on")

    async def async_turn_off(self) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off")
