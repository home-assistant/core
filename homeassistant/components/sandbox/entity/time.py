"""Sandbox proxy for time entities."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity

from . import SandboxProxyEntity


class SandboxTimeEntity(SandboxProxyEntity, TimeEntity):
    """Proxy for a time entity in a sandbox."""

    @property
    def native_value(self):
        """Return the current time value."""
        val = self._state_cache.get("state")
        if val is None:
            return None
        if isinstance(val, str):
            return time.fromisoformat(val)
        return val

    async def async_set_value(self, value) -> None:
        """Forward set_value to sandbox."""
        await self._forward_method("async_set_value", value=value.isoformat())
