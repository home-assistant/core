"""Coordinator for PG LAB Electronics."""

from __future__ import annotations

from typing import Any

from pypglab.device import Device as PyPGLabDevice
from pypglab.sensor import Sensor as PyPGLabSensors

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


class PGLabSensorsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to update Sensor Entities when receiving new data."""

    def __init__(self, hass: HomeAssistant, pglab_device: PyPGLabDevice) -> None:
        """Initialize."""

        # get a reference of PG Lab device internal sensors state
        self._sensors: PyPGLabSensors = pglab_device.sensors

        super().__init__(hass, LOGGER, name=DOMAIN, always_update=True)

    @callback
    def _new_sensors_data(self, payload: str) -> None:
        """Handle new sensor data."""

        # notify all listeners that new sensor values are available
        self.async_set_updated_data(self._sensors.state)

    async def subscribe_topics(self) -> None:
        """Subscribe the sensors state to be notifty from MQTT update messages."""

        # subscribe to the pypglab sensors to receive updates from the mqtt broker
        # when a new sensor values are available
        await self._sensors.subscribe_topics()

        # set the callback to be called when a new sensor values are available
        self._sensors.set_on_state_callback(self._new_sensors_data)

    def get_sensor_value(self, sensor_key: str) -> Any:
        """Return the value of a sensor."""
        if self.data:
            return self.data[sensor_key]
        return None
