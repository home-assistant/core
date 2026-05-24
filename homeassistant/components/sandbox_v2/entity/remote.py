"""Sandbox v2 proxy for ``remote`` entities."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from homeassistant.components.remote import (
    ATTR_ACTIVITY_LIST,
    ATTR_CURRENT_ACTIVITY,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.const import STATE_ON

from . import SandboxProxyEntity

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxRemoteEntity(SandboxProxyEntity, RemoteEntity):
    """Proxy for a ``remote`` entity in a sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``RemoteEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = RemoteEntityFeature(
            description.supported_features or 0
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the cached state is ``on``."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == STATE_ON

    @property
    def current_activity(self) -> str | None:
        """Return the cached current activity."""
        return self._state_cache.get(ATTR_CURRENT_ACTIVITY)

    @property
    def activity_list(self) -> list[str] | None:
        """Return the configured activity list."""
        value = self.description.capabilities.get(ATTR_ACTIVITY_LIST)
        return list(value) if value else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on."""
        await self._call_service("turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off."""
        await self._call_service("turn_off", **kwargs)

    async def async_toggle(self, **kwargs: Any) -> None:
        """Forward toggle."""
        await self._call_service("toggle", **kwargs)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Forward send_command."""
        await self._call_service("send_command", command=list(command), **kwargs)

    async def async_learn_command(self, **kwargs: Any) -> None:
        """Forward learn_command."""
        await self._call_service("learn_command", **kwargs)

    async def async_delete_command(self, **kwargs: Any) -> None:
        """Forward delete_command."""
        await self._call_service("delete_command", **kwargs)
