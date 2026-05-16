"""Sandbox proxy for text entities."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxTextEntity(SandboxProxyEntity, TextEntity):
    """Proxy for a text entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy text entity."""
        super().__init__(description, manager)
        caps = description.capabilities
        if (native_min := caps.get("native_min")) is not None:
            self._attr_native_min = native_min
        if (native_max := caps.get("native_max")) is not None:
            self._attr_native_max = native_max
        if mode := caps.get("mode"):
            self._attr_mode = TextMode(mode)
        if pattern := caps.get("pattern"):
            self._attr_pattern = pattern

    @property
    def native_value(self) -> str | None:
        """Return the current value."""
        return self._state_cache.get("state")

    async def async_set_value(self, value: str) -> None:
        """Forward set_value to sandbox."""
        await self._forward_method("async_set_value", value=value)
