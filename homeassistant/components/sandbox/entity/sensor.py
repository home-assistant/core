"""Sandbox proxy for sensor entities."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxSensorEntity(SandboxProxyEntity, SensorEntity):
    """Proxy for a sensor entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy sensor entity."""
        super().__init__(description, manager)
        if description.state_class:
            self._attr_state_class = SensorStateClass(description.state_class)
        unit = description.capabilities.get("native_unit_of_measurement")
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> str | int | float | None:
        """Return the sensor value."""
        return self._state_cache.get("state")
