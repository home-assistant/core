"""Sandbox proxy for ``notify`` entities."""

from typing import Any

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.core import Context

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxNotifyEntity(SandboxProxyEntity, NotifyEntity):
    """Proxy for a ``notify`` entity in a sandbox."""

    _features_flag = NotifyEntityFeature

    def sandbox_apply_state(
        self,
        state: str | None,
        attributes: dict[str, Any],
        context: Context | None = None,
    ) -> None:
        """Mirror ``__last_notified_isoformat`` for state computation."""
        if state is not None:
            # pylint: disable-next=attribute-defined-outside-init
            self._NotifyEntity__last_notified_isoformat = state
        super().sandbox_apply_state(state, attributes, context)

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Forward send_message."""
        await self._call_service("send_message", message=message, title=title)
