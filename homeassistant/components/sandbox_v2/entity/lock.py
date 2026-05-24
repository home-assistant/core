"""Sandbox v2 proxy for ``lock`` entities."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.lock import LockEntity, LockEntityFeature, LockState

from . import SandboxProxyEntity

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxLockEntity(SandboxProxyEntity, LockEntity):
    """Proxy for a ``lock`` entity in a sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``LockEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = LockEntityFeature(
            description.supported_features or 0
        )

    @property
    def is_locked(self) -> bool | None:
        """Derive locked from cached state."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == LockState.LOCKED

    @property
    def is_locking(self) -> bool | None:
        """True iff cached state is ``locking``."""
        return self._state_cache.get("state") == LockState.LOCKING

    @property
    def is_unlocking(self) -> bool | None:
        """True iff cached state is ``unlocking``."""
        return self._state_cache.get("state") == LockState.UNLOCKING

    @property
    def is_open(self) -> bool | None:
        """True iff cached state is ``open``."""
        return self._state_cache.get("state") == LockState.OPEN

    @property
    def is_opening(self) -> bool | None:
        """True iff cached state is ``opening``."""
        return self._state_cache.get("state") == LockState.OPENING

    @property
    def is_jammed(self) -> bool | None:
        """True iff cached state is ``jammed``."""
        return self._state_cache.get("state") == LockState.JAMMED

    @property
    def code_format(self) -> str | None:
        """Return the configured code format."""
        value = self.description.capabilities.get("code_format")
        return str(value) if value is not None else None

    @property
    def changed_by(self) -> str | None:
        """Return the cached changed_by."""
        return self._state_cache.get("changed_by")

    async def async_lock(self, **kwargs: Any) -> None:
        """Forward lock."""
        await self._call_service("lock", **kwargs)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Forward unlock."""
        await self._call_service("unlock", **kwargs)

    async def async_open(self, **kwargs: Any) -> None:
        """Forward open."""
        await self._call_service("open", **kwargs)
