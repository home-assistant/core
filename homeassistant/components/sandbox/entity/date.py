"""Sandbox proxy for ``date`` entities."""

from datetime import date
from typing import override

from homeassistant.components.date import DateEntity
from homeassistant.util import dt as dt_util

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxDateEntity(SandboxProxyEntity, DateEntity):
    """Proxy for a ``date`` entity in a sandbox."""

    @property
    @override
    def native_value(self) -> date | None:
        """Parse the cached ISO date string."""
        value = self._state_cache.get("state")
        if not isinstance(value, str) or value in ("unavailable", "unknown"):
            return None
        try:
            return dt_util.parse_date(value)
        except TypeError, ValueError:
            return None

    @override
    async def async_set_value(self, value: date) -> None:
        """Forward set_value as ``date.set_value``."""
        await self._call_service("set_value", date=value.isoformat())
