"""Sandbox proxy for notify entities."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxNotifyEntity(SandboxProxyEntity, NotifyEntity):
    """Proxy for a notify entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy notify entity."""
        super().__init__(description, manager)
        self._attr_supported_features = NotifyEntityFeature(
            description.supported_features
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Forward send_message to sandbox."""
        await self._forward_method("async_send_message", message=message, title=title)
