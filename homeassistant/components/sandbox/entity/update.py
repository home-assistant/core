"""Sandbox proxy for update entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxUpdateEntity(SandboxProxyEntity, UpdateEntity):
    """Proxy for an update entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy update entity."""
        super().__init__(description, manager)
        self._attr_supported_features = UpdateEntityFeature(
            description.supported_features
        )

    @property
    def installed_version(self) -> str | None:
        """Return the installed version."""
        return self._state_cache.get("installed_version")

    @property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        return self._state_cache.get("latest_version")

    @property
    def title(self) -> str | None:
        """Return the title."""
        return self._state_cache.get("title")

    @property
    def release_summary(self) -> str | None:
        """Return the release summary."""
        return self._state_cache.get("release_summary")

    @property
    def release_url(self) -> str | None:
        """Return the release URL."""
        return self._state_cache.get("release_url")

    @property
    def in_progress(self) -> bool | int | None:
        """Return if update is in progress."""
        return self._state_cache.get("in_progress")

    @property
    def auto_update(self) -> bool:
        """Return if auto-update is enabled."""
        return self._state_cache.get("auto_update", False)

    async def async_install(self, version: str | None = None, backup: bool = False, **kwargs: Any) -> None:
        """Forward install to sandbox."""
        await self._forward_method("async_install", version=version, backup=backup, **kwargs)
