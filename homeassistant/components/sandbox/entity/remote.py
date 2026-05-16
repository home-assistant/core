"""Sandbox proxy for remote entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxRemoteEntity(SandboxProxyEntity, RemoteEntity):
    """Proxy for a remote entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy remote entity."""
        super().__init__(description, manager)
        self._attr_supported_features = RemoteEntityFeature(
            description.supported_features
        )
        if activity_list := description.capabilities.get("activity_list"):
            self._attr_activity_list = activity_list

    @property
    def is_on(self) -> bool | None:
        """Return if the remote is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    @property
    def current_activity(self) -> str | None:
        """Return the current activity."""
        return self._state_cache.get("current_activity")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)

    async def async_send_command(self, command: list[str], **kwargs: Any) -> None:
        """Forward send_command to sandbox."""
        await self._forward_method("async_send_command", command=command, **kwargs)
