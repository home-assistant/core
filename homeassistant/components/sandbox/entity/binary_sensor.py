"""Sandbox proxy for ``binary_sensor`` entities."""

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_ON

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxBinarySensorEntity(SandboxProxyEntity, BinarySensorEntity):
    """Proxy for a ``binary_sensor`` entity in a sandbox."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the cached state is ``on``."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == STATE_ON
