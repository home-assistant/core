"""Sandbox v2 proxy for ``binary_sensor`` entities."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_ON

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxBinarySensorEntity(SandboxProxyEntity, BinarySensorEntity):
    """Proxy for a ``binary_sensor`` entity in a sandbox."""

    @property
    def is_on(self) -> bool | None:
        """Return whether the cached state is ``on``."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == STATE_ON
