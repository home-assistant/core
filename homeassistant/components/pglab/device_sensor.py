"""Device Sensor for PG LAB Electronics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypglab.device import Device as PyPGLabDevice
from pypglab.sensor import Sensor as PyPGLabSensors

from homeassistant.core import callback

if TYPE_CHECKING:
    from .entity import PGLabEntity


class PGLabDeviceSensor:
    """Keeps PGLab device sensor update."""

    def __init__(self, pglab_device: PyPGLabDevice) -> None:
        """Initialize the device sensor."""

        # get a reference of PG Lab device internal sensors state
        self._sensors: PyPGLabSensors = pglab_device.sensors

        self._ha_sensors: list[PGLabEntity] = []  # list of HA entity sensors

    async def subscribe_topics(self):
        """Subscribe to the device sensors topics."""
        self._sensors.set_on_state_callback(self.state_updated)
        await self._sensors.subscribe_topics()

    def add_ha_sensor(self, entity: PGLabEntity) -> None:
        """Add a new HA sensor to the list."""
        self._ha_sensors.append(entity)

    def remove_ha_sensor(self, entity: PGLabEntity) -> None:
        """Remove a HA sensor from the list."""
        self._ha_sensors.remove(entity)

    @callback
    def state_updated(self, payload: str) -> None:
        """Handle state updates."""

        # notify all HA sensors that PG LAB device sensor fields have been updated
        for s in self._ha_sensors:
            s.state_updated(payload)

    @property
    def state(self) -> dict:
        """Return the device sensors state."""
        return self._sensors.state

    @property
    def sensors(self) -> PyPGLabSensors:
        """Return the pypglab device sensors."""
        return self._sensors
