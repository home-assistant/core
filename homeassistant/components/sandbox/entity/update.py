"""Sandbox proxy for ``update`` entities."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    UpdateEntity,
    UpdateEntityFeature,
)

from . import SandboxProxyEntity, raise_not_proxied

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription

# These attribute names are emitted by ``UpdateEntity.state_attributes``
# (see ``components/update/__init__.py``). They're defined in
# ``update.const`` but not exported from the package root, so we hold the
# string keys locally rather than chase the pylint / mypy conflict on
# importing from ``.const``.
_ATTR_AUTO_UPDATE = "auto_update"
_ATTR_IN_PROGRESS = "in_progress"
_ATTR_RELEASE_SUMMARY = "release_summary"
_ATTR_RELEASE_URL = "release_url"
_ATTR_TITLE = "title"
_ATTR_UPDATE_PERCENTAGE = "update_percentage"


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxUpdateEntity(SandboxProxyEntity, UpdateEntity):
    """Proxy for an ``update`` entity in a sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``UpdateEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = UpdateEntityFeature(
            description.supported_features or 0
        )

    @property
    def installed_version(self) -> str | None:
        """Return the cached installed version."""
        return self._state_cache.get(ATTR_INSTALLED_VERSION)

    @property
    def latest_version(self) -> str | None:
        """Return the cached latest version."""
        return self._state_cache.get(ATTR_LATEST_VERSION)

    @property
    def release_summary(self) -> str | None:
        """Return the cached release summary."""
        return self._state_cache.get(_ATTR_RELEASE_SUMMARY)

    @property
    def release_url(self) -> str | None:
        """Return the cached release URL."""
        return self._state_cache.get(_ATTR_RELEASE_URL)

    @property
    def title(self) -> str | None:
        """Return the cached title."""
        return self._state_cache.get(_ATTR_TITLE)

    @property
    def in_progress(self) -> bool | None:
        """Return the cached progress flag."""
        value = self._state_cache.get(_ATTR_IN_PROGRESS)
        return None if value is None else bool(value)

    @property
    def update_percentage(self) -> int | float | None:
        """Return the cached progress percentage."""
        value = self._state_cache.get(_ATTR_UPDATE_PERCENTAGE)
        if value is None:
            return None
        try:
            return float(value)
        except TypeError, ValueError:
            return None

    @property
    def auto_update(self) -> bool:
        """Return the cached auto-update flag."""
        return bool(self._state_cache.get(_ATTR_AUTO_UPDATE, False))

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Forward install."""
        payload: dict[str, Any] = {"backup": backup, **kwargs}
        if version is not None:
            payload["version"] = version
        await self._call_service("install", **payload)

    async def async_release_notes(self) -> str | None:
        """Raise — ``update/release_notes`` is a WS query, not yet proxied."""
        raise_not_proxied("Fetching update release notes")
