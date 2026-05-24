"""Sandbox v2 proxy for ``notify`` entities."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature

from . import SandboxProxyEntity

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxNotifyEntity(SandboxProxyEntity, NotifyEntity):
    """Proxy for a ``notify`` entity in a sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``NotifyEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = NotifyEntityFeature(
            description.supported_features or 0
        )

    def sandbox_apply_state(
        self, state: str | None, attributes: dict[str, Any]
    ) -> None:
        """Mirror ``__last_notified_isoformat`` for state computation."""
        if state is not None:
            # pylint: disable-next=attribute-defined-outside-init
            self._NotifyEntity__last_notified_isoformat = state
        super().sandbox_apply_state(state, attributes)

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Forward send_message."""
        await self._call_service("send_message", message=message, title=title)
