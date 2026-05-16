"""Sandbox proxy for siren entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.siren import SirenEntity, SirenEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxSirenEntity(SandboxProxyEntity, SirenEntity):
    """Proxy for a siren entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy siren entity."""
        super().__init__(description, manager)
        self._attr_supported_features = SirenEntityFeature(
            description.supported_features
        )
        if available_tones := description.capabilities.get("available_tones"):
            self._attr_available_tones = available_tones

    @property
    def is_on(self) -> bool | None:
        """Return if the siren is on."""
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
