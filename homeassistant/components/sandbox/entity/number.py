"""Sandbox proxy for ``number`` entities."""

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    NumberEntity,
    NumberMode,
)

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxNumberEntity(SandboxProxyEntity, NumberEntity):
    """Proxy for a ``number`` entity in a sandbox."""

    @property
    def native_value(self) -> float | None:
        """Parse the cached number state."""
        value = self._state_cache.get("state")
        if value is None or value in ("unavailable", "unknown"):
            return None
        try:
            return float(value)
        except TypeError, ValueError:
            return None

    @property
    def native_min_value(self) -> float:
        """Return the configured minimum."""
        value = self.description.capabilities.get(ATTR_MIN)
        return float(value) if value is not None else super().native_min_value

    @property
    def native_max_value(self) -> float:
        """Return the configured maximum."""
        value = self.description.capabilities.get(ATTR_MAX)
        return float(value) if value is not None else super().native_max_value

    @property
    def native_step(self) -> float | None:
        """Return the configured step."""
        value = self.description.capabilities.get(ATTR_STEP)
        return float(value) if value is not None else None

    @property
    def mode(self) -> NumberMode:
        """Return the configured display mode."""
        value = self.description.capabilities.get("mode")
        if value is None:
            return NumberMode.AUTO
        try:
            return NumberMode(value)
        except ValueError:
            return NumberMode.AUTO

    async def async_set_native_value(self, value: float) -> None:
        """Forward set_value as ``number.set_value``."""
        await self._call_service("set_value", value=value)
