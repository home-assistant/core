"""Sandbox proxy for button entities."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from . import SandboxProxyEntity


class SandboxButtonEntity(SandboxProxyEntity, ButtonEntity):
    """Proxy for a button entity in a sandbox."""

    async def async_press(self) -> None:
        """Forward press to sandbox."""
        await self._forward_method("async_press")
