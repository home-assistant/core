"""Sandbox proxy for ``siren`` entities."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.siren import (
    ATTR_AVAILABLE_TONES,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.const import STATE_ON

from . import SandboxProxyEntity

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxSirenEntity(SandboxProxyEntity, SirenEntity):
    """Proxy for a ``siren`` entity in a sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``SirenEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = SirenEntityFeature(
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
    def available_tones(self) -> list[int | str] | dict[int, str] | None:
        """Return the configured available tones."""
        return self.description.capabilities.get(ATTR_AVAILABLE_TONES)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on."""
        await self._call_service("turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off."""
        await self._call_service("turn_off", **kwargs)

    async def async_toggle(self, **kwargs: Any) -> None:
        """Forward toggle."""
        await self._call_service("toggle", **kwargs)
