"""Sandbox proxy for ``siren`` entities."""

from typing import Any, override

from homeassistant.components.siren import (
    ATTR_AVAILABLE_TONES,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.const import STATE_ON

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxSirenEntity(SandboxProxyEntity, SirenEntity):
    """Proxy for a ``siren`` entity in a sandbox."""

    _features_flag = SirenEntityFeature

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the cached state is ``on``."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == STATE_ON

    @property
    @override
    def available_tones(self) -> list[int | str] | dict[int, str] | None:
        """Return the configured available tones."""
        return self.description.capabilities.get(ATTR_AVAILABLE_TONES)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on."""
        await self._call_service("turn_on", **kwargs)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off."""
        await self._call_service("turn_off", **kwargs)

    @override
    async def async_toggle(self, **kwargs: Any) -> None:
        """Forward toggle."""
        await self._call_service("toggle", **kwargs)
