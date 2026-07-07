"""Sandbox proxy for ``time`` entities."""

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.util import dt as dt_util

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxTimeEntity(SandboxProxyEntity, TimeEntity):
    """Proxy for a ``time`` entity in a sandbox."""

    @property
    def native_value(self) -> time | None:
        """Parse the cached ISO time string."""
        value = self._state_cache.get("state")
        if not isinstance(value, str) or value in ("unavailable", "unknown"):
            return None
        try:
            return dt_util.parse_time(value)
        except TypeError, ValueError:
            return None

    async def async_set_value(self, value: time) -> None:
        """Forward set_value as ``time.set_value``."""
        await self._call_service("set_value", time=value.isoformat())
