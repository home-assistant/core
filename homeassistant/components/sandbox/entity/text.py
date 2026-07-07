"""Sandbox proxy for ``text`` entities."""

from homeassistant.components.text import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_PATTERN,
    TextEntity,
    TextMode,
)

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxTextEntity(SandboxProxyEntity, TextEntity):
    """Proxy for a ``text`` entity in a sandbox."""

    @property
    def native_value(self) -> str | None:
        """Return the cached text value."""
        value = self._state_cache.get("state")
        if value in (None, "unavailable", "unknown"):
            return None
        return str(value)

    @property
    def native_min(self) -> int:
        """Return the configured minimum length."""
        value = self.description.capabilities.get(ATTR_MIN)
        return int(value) if value is not None else 0

    @property
    def native_max(self) -> int:
        """Return the configured maximum length."""
        value = self.description.capabilities.get(ATTR_MAX)
        return int(value) if value is not None else super().native_max

    @property
    def pattern(self) -> str | None:
        """Return the configured pattern."""
        value = self.description.capabilities.get(ATTR_PATTERN)
        return str(value) if value is not None else None

    @property
    def mode(self) -> TextMode:
        """Return the configured display mode."""
        value = self.description.capabilities.get(ATTR_MODE)
        if value is None:
            return TextMode.TEXT
        try:
            return TextMode(value)
        except ValueError:
            return TextMode.TEXT

    async def async_set_value(self, value: str) -> None:
        """Forward set_value as ``text.set_value``."""
        await self._call_service("set_value", value=value)
