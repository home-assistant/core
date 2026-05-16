"""Sandbox proxy for scene entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.scene import Scene

from . import SandboxProxyEntity


class SandboxSceneEntity(SandboxProxyEntity, Scene):
    """Proxy for a scene entity in a sandbox."""

    async def async_activate(self, **kwargs: Any) -> None:
        """Forward activate to sandbox."""
        await self._forward_method("async_activate", **kwargs)
