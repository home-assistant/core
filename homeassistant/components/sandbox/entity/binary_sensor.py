"""Sandbox proxy for binary_sensor entities."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import SandboxProxyEntity


class SandboxBinarySensorEntity(SandboxProxyEntity, BinarySensorEntity):
    """Proxy for a binary_sensor entity in a sandbox."""

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"
