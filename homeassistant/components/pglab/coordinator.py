"""Coordinator for PG LAB Electronics."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from pypglab.const import SENSOR_REBOOT_TIME, SENSOR_TEMPERATURE, SENSOR_VOLTAGE
from pypglab.device import Device as PyPGLabDevice
from pypglab.sensor import StatusSensor as PyPGLabSensors

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import PGLabConfigEntry


class PGLabSensorsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to update Sensor Entities when receiving new data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PGLabConfigEntry,
        pglab_device: PyPGLabDevice,
    ) -> None:
        """Initialize."""

        # get a reference of PG Lab device internal sensors state
        self._sensors: PyPGLabSensors = pglab_device.status_sensor

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
        )

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

    def get_sensor_value(self, sensor_key: str) -> float | datetime | None:
        """Return the value of a sensor."""

        if self.data:
            value = self.data[sensor_key]

            if (sensor_key == SENSOR_REBOOT_TIME) and value:
                # convert the reboot time to a datetime object
                return utcnow() - timedelta(seconds=value)

            if (sensor_key == SENSOR_TEMPERATURE) and value:
                # convert the temperature value to a float
                return float(value)

            if (sensor_key == SENSOR_VOLTAGE) and value:
                # convert the voltage value to a float
                return float(value)

        return None
