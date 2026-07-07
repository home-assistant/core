"""Sandbox proxy for ``cover`` entities."""

from typing import Any, override

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_IS_CLOSED,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxCoverEntity(SandboxProxyEntity, CoverEntity):
    """Proxy for a ``cover`` entity in a sandbox."""

    _features_flag = CoverEntityFeature

    @property
    @override
    def is_opening(self) -> bool | None:
        """True iff the cached state is ``opening``."""
        return self._state_cache.get("state") == CoverState.OPENING

    @property
    @override
    def is_closing(self) -> bool | None:
        """True iff the cached state is ``closing``."""
        return self._state_cache.get("state") == CoverState.CLOSING

    @property
    @override
    def is_closed(self) -> bool | None:
        """Derive closed from cached state / ATTR_IS_CLOSED."""
        if (value := self._state_cache.get(ATTR_IS_CLOSED)) is not None:
            return bool(value)
        state = self._state_cache.get("state")
        if state == CoverState.CLOSED:
            return True
        if state in (CoverState.OPEN, CoverState.OPENING, CoverState.CLOSING):
            return False
        return None

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return the cached current position."""
        value = self._state_cache.get(ATTR_CURRENT_POSITION)
        return None if value is None else int(value)

    @property
    @override
    def current_cover_tilt_position(self) -> int | None:
        """Return the cached current tilt position."""
        value = self._state_cache.get(ATTR_CURRENT_TILT_POSITION)
        return None if value is None else int(value)

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Forward open_cover."""
        await self._call_service("open_cover", **kwargs)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Forward close_cover."""
        await self._call_service("close_cover", **kwargs)

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Forward set_cover_position."""
        await self._call_service("set_cover_position", **kwargs)

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Forward stop_cover."""
        await self._call_service("stop_cover", **kwargs)

    @override
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Forward open_cover_tilt."""
        await self._call_service("open_cover_tilt", **kwargs)

    @override
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Forward close_cover_tilt."""
        await self._call_service("close_cover_tilt", **kwargs)

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Forward set_cover_tilt_position."""
        await self._call_service("set_cover_tilt_position", **kwargs)

    @override
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Forward stop_cover_tilt."""
        await self._call_service("stop_cover_tilt", **kwargs)
