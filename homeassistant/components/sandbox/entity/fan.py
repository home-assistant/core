"""Sandbox proxy for fan entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxFanEntity(SandboxProxyEntity, FanEntity):
    """Proxy for a fan entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy fan entity."""
        super().__init__(description, manager)
        self._attr_supported_features = FanEntityFeature(
            description.supported_features
        )
        if preset_modes := description.capabilities.get("preset_modes"):
            self._attr_preset_modes = preset_modes
        if speed_count := description.capabilities.get("speed_count"):
            self._attr_speed_count = speed_count

    @property
    def is_on(self) -> bool | None:
        """Return if the fan is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return self._state_cache.get("percentage")

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._state_cache.get("preset_mode")

    @property
    def current_direction(self) -> str | None:
        """Return the current direction."""
        return self._state_cache.get("current_direction")

    @property
    def oscillating(self) -> bool | None:
        """Return if the fan is oscillating."""
        return self._state_cache.get("oscillating")

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", percentage=percentage, preset_mode=preset_mode, **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)

    async def async_set_percentage(self, percentage: int) -> None:
        """Forward set_percentage to sandbox."""
        await self._forward_method("async_set_percentage", percentage=percentage)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Forward set_preset_mode to sandbox."""
        await self._forward_method("async_set_preset_mode", preset_mode=preset_mode)

    async def async_set_direction(self, direction: str) -> None:
        """Forward set_direction to sandbox."""
        await self._forward_method("async_set_direction", direction=direction)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Forward oscillate to sandbox."""
        await self._forward_method("async_oscillate", oscillating=oscillating)
