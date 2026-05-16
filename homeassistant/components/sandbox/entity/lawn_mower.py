"""Sandbox proxy for lawn_mower entities."""

from __future__ import annotations

from homeassistant.components.lawn_mower import LawnMowerActivity, LawnMowerEntity, LawnMowerEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxLawnMowerEntity(SandboxProxyEntity, LawnMowerEntity):
    """Proxy for a lawn_mower entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy lawn mower entity."""
        super().__init__(description, manager)
        self._attr_supported_features = LawnMowerEntityFeature(
            description.supported_features
        )

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the current activity."""
        val = self._state_cache.get("activity")
        if val is None:
            return None
        return LawnMowerActivity(val)

    async def async_start_mowing(self) -> None:
        """Forward start_mowing to sandbox."""
        await self._forward_method("async_start_mowing")

    async def async_dock(self) -> None:
        """Forward dock to sandbox."""
        await self._forward_method("async_dock")

    async def async_pause(self) -> None:
        """Forward pause to sandbox."""
        await self._forward_method("async_pause")
