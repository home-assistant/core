"""Sandbox proxy for cover entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import CoverEntity, CoverEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxCoverEntity(SandboxProxyEntity, CoverEntity):
    """Proxy for a cover entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy cover entity."""
        super().__init__(description, manager)
        self._attr_supported_features = CoverEntityFeature(
            description.supported_features
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "closed"

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        return self._state_cache.get("is_opening")

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        return self._state_cache.get("is_closing")

    @property
    def current_cover_position(self) -> int | None:
        """Return the current cover position."""
        return self._state_cache.get("current_cover_position")

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position."""
        return self._state_cache.get("current_cover_tilt_position")

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Forward open_cover to sandbox."""
        await self._forward_method("async_open_cover", **kwargs)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Forward close_cover to sandbox."""
        await self._forward_method("async_close_cover", **kwargs)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Forward stop_cover to sandbox."""
        await self._forward_method("async_stop_cover", **kwargs)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Forward set_cover_position to sandbox."""
        await self._forward_method("async_set_cover_position", **kwargs)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Forward open_cover_tilt to sandbox."""
        await self._forward_method("async_open_cover_tilt", **kwargs)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Forward close_cover_tilt to sandbox."""
        await self._forward_method("async_close_cover_tilt", **kwargs)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Forward stop_cover_tilt to sandbox."""
        await self._forward_method("async_stop_cover_tilt", **kwargs)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Forward set_cover_tilt_position to sandbox."""
        await self._forward_method("async_set_cover_tilt_position", **kwargs)
