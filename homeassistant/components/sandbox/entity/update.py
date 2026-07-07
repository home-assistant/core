"""Sandbox proxy for ``update`` entities."""

from typing import Any, override

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    UpdateEntity,
    UpdateEntityFeature,
)

from . import SandboxProxyEntity

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

    _features_flag = UpdateEntityFeature

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the cached installed version."""
        return self._state_cache.get(ATTR_INSTALLED_VERSION)

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the cached latest version."""
        return self._state_cache.get(ATTR_LATEST_VERSION)

    @property
    @override
    def release_summary(self) -> str | None:
        """Return the cached release summary."""
        return self._state_cache.get(_ATTR_RELEASE_SUMMARY)

    @property
    @override
    def release_url(self) -> str | None:
        """Return the cached release URL."""
        return self._state_cache.get(_ATTR_RELEASE_URL)

    @property
    @override
    def title(self) -> str | None:
        """Return the cached title."""
        return self._state_cache.get(_ATTR_TITLE)

    @property
    @override
    def in_progress(self) -> bool | None:
        """Return the cached progress flag."""
        value = self._state_cache.get(_ATTR_IN_PROGRESS)
        return None if value is None else bool(value)

    @property
    @override
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
    @override
    def auto_update(self) -> bool:
        """Return the cached auto-update flag."""
        return bool(self._state_cache.get(_ATTR_AUTO_UPDATE, False))

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Forward install."""
        payload: dict[str, Any] = {"backup": backup, **kwargs}
        if version is not None:
            payload["version"] = version
        await self._call_service("install", **payload)

    @override
    async def async_release_notes(self) -> str | None:
        """Return the release notes via ``EntityQuery`` (a plain str/None)."""
        return await self._entity_query("async_release_notes")
