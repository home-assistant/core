"""Sandbox proxy for lock entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxLockEntity(SandboxProxyEntity, LockEntity):
    """Proxy for a lock entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy lock entity."""
        super().__init__(description, manager)
        self._attr_supported_features = LockEntityFeature(
            description.supported_features
        )

    @property
    def is_locked(self) -> bool | None:
        """Return if the lock is locked."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "locked"

    @property
    def is_locking(self) -> bool | None:
        """Return if the lock is locking."""
        return self._state_cache.get("is_locking")

    @property
    def is_unlocking(self) -> bool | None:
        """Return if the lock is unlocking."""
        return self._state_cache.get("is_unlocking")

    @property
    def is_jammed(self) -> bool | None:
        """Return if the lock is jammed."""
        return self._state_cache.get("is_jammed")

    @property
    def is_open(self) -> bool | None:
        """Return if the lock is open."""
        return self._state_cache.get("is_open")

    async def async_lock(self, **kwargs: Any) -> None:
        """Forward lock to sandbox."""
        await self._forward_method("async_lock", **kwargs)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Forward unlock to sandbox."""
        await self._forward_method("async_unlock", **kwargs)

    async def async_open(self, **kwargs: Any) -> None:
        """Forward open to sandbox."""
        await self._forward_method("async_open", **kwargs)
