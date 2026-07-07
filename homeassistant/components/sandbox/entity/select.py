"""Sandbox proxy for ``select`` entities."""

from typing import override

from homeassistant.components.select import ATTR_OPTIONS, SelectEntity

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxSelectEntity(SandboxProxyEntity, SelectEntity):
    """Proxy for a ``select`` entity in a sandbox."""

    @property
    @override
    def current_option(self) -> str | None:
        """Return the cached current option."""
        value = self._state_cache.get("state")
        if value in (None, "unavailable", "unknown"):
            return None
        return value

    @property
    @override
    def options(self) -> list[str]:
        """Return the cached options list."""
        value = self.description.capabilities.get(ATTR_OPTIONS) or []
        return list(value)

    @override
    async def async_select_option(self, option: str) -> None:
        """Forward select_option."""
        await self._call_service("select_option", option=option)
