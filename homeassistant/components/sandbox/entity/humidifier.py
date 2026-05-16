"""Sandbox proxy for humidifier entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.humidifier import HumidifierEntity, HumidifierEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxHumidifierEntity(SandboxProxyEntity, HumidifierEntity):
    """Proxy for a humidifier entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy humidifier entity."""
        super().__init__(description, manager)
        self._attr_supported_features = HumidifierEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if available_modes := caps.get("available_modes"):
            self._attr_available_modes = available_modes
        if (min_humidity := caps.get("min_humidity")) is not None:
            self._attr_min_humidity = min_humidity
        if (max_humidity := caps.get("max_humidity")) is not None:
            self._attr_max_humidity = max_humidity

    @property
    def is_on(self) -> bool | None:
        """Return if the humidifier is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._state_cache.get("current_humidity")

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity."""
        return self._state_cache.get("target_humidity")

    @property
    def mode(self) -> str | None:
        """Return the current mode."""
        return self._state_cache.get("mode")

    @property
    def action(self) -> str | None:
        """Return the current action."""
        return self._state_cache.get("action")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)

    async def async_set_humidity(self, humidity: int) -> None:
        """Forward set_humidity to sandbox."""
        await self._forward_method("async_set_humidity", humidity=humidity)

    async def async_set_mode(self, mode: str) -> None:
        """Forward set_mode to sandbox."""
        await self._forward_method("async_set_mode", mode=mode)
