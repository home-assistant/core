"""Sandbox proxy for select entities."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxSelectEntity(SandboxProxyEntity, SelectEntity):
    """Proxy for a select entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy select entity."""
        super().__init__(description, manager)
        self._attr_options = description.capabilities.get("options", [])

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self._state_cache.get("state")

    async def async_select_option(self, option: str) -> None:
        """Forward select_option to sandbox."""
        await self._forward_method("async_select_option", option=option)
