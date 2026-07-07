"""Sandbox proxy for ``device_tracker`` entities."""

from typing import override

from homeassistant.components.device_tracker import (
    ATTR_SOURCE_TYPE,
    BaseTrackerEntity,
    SourceType,
)

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxDeviceTrackerEntity(SandboxProxyEntity, BaseTrackerEntity):
    """Proxy for a ``device_tracker`` entity in a sandbox.

    Subclasses the abstract :class:`BaseTrackerEntity` so we can override
    both ``state`` and ``state_attributes`` (the GPS-specific
    :class:`TrackerEntity` marks ``state_attributes`` ``@final``).
    """

    @property
    @override
    def state(self) -> str | None:
        """Mirror the sandbox-side state directly."""
        return self._state_cache.get("state")

    @property
    @override
    def source_type(self) -> SourceType:
        """Return the cached source_type (gps / router / bluetooth / …)."""
        value = self._state_cache.get(
            ATTR_SOURCE_TYPE,
            self.description.capabilities.get(ATTR_SOURCE_TYPE),
        )
        if value is None:
            return SourceType.ROUTER
        try:
            return SourceType(value)
        except ValueError:
            return SourceType.ROUTER
