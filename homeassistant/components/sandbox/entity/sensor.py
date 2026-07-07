"""Sandbox proxy for ``sensor`` entities."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxSensorEntity(SandboxProxyEntity, SensorEntity):
    """Proxy for a ``sensor`` entity in a sandbox."""

    @property
    def native_value(self) -> str | int | float | None:
        """Return the cached state as the sensor's native value."""
        return self._state_cache.get("state")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the cached unit of measurement."""
        return self._state_cache.get(
            ATTR_UNIT_OF_MEASUREMENT,
            self.description.capabilities.get(ATTR_UNIT_OF_MEASUREMENT),
        )
