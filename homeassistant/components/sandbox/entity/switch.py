"""Sandbox proxy for switch entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity

from . import SandboxProxyEntity


class SandboxSwitchEntity(SandboxProxyEntity, SwitchEntity):
    """Proxy for a switch entity in a sandbox."""

    @property
    def is_on(self) -> bool | None:
        """Return if the switch is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)
