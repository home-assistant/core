"""Platform for FAA Delays sensor component."""
import logging

from aiohttp import ClientConnectionError

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN, FAA_BINARY_SENSORS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a FAA sensor based on a config entry."""
    faadata = hass.data[DOMAIN][entry.entry_id]

    binary_sensors = []
    for kind, attrs in FAA_BINARY_SENSORS.items():
        name, icon = attrs
        binary_sensors.append(
            FAABinarySensor(faadata, kind, name, icon, entry.entry_id)
        )

    async_add_entities(binary_sensors, True)


class FAABinarySensor(BinarySensorEntity):
    """Define a binary sensor for FAA Delays."""

    def __init__(self, faadata, sensor_type, name, icon, entry_id):
        """Initialize the sensor."""

        self._data = faadata
        self._entry_id = entry_id
        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None
        self._id = faadata._client.iata
        self._available = True
        self._attrs = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._id} {self._name}"

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def state(self):
        """Return the status of the sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._id}_{self._sensor_type}"

    @property
    def device_state_attributes(self):
        """Return attributes for sensor."""
        return self._attrs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_update(self):
        """Update the data from the FAA API."""

        try:
            await self._data.async_update()
        except ClientConnectionError as err:
            _LOGGER.error("Connection error during data update: %s", err)
            self._available = False
            return

        if self._sensor_type == "GROUND_DELAY":
            self._state = self._data._client.ground_delay.status
            self._attrs["average"] = self._data._client.ground_delay.average
            self._attrs["reason"] = self._data._client.ground_delay.reason
        elif self._sensor_type == "GROUND_STOP":
            self._state = self._data._client.ground_stop.status
            self._attrs["endtime"] = self._data._client.ground_stop.endtime
            self._attrs["reason"] = self._data._client.ground_stop.reason
        elif self._sensor_type == "DEPART_DELAY":
            self._state = self._data._client.depart_delay.status
            self._attrs["minimum"] = self._data._client.depart_delay.minimum
            self._attrs["maximum"] = self._data._client.depart_delay.maximum
            self._attrs["trend"] = self._data._client.depart_delay.trend
            self._attrs["reason"] = self._data._client.depart_delay.reason
        elif self._sensor_type == "ARRIVE_DELAY":
            self._state = self._data._client.arrive_delay.status
            self._attrs["minimum"] = self._data._client.arrive_delay.minimum
            self._attrs["maximum"] = self._data._client.arrive_delay.maximum
            self._attrs["trend"] = self._data._client.arrive_delay.trend
            self._attrs["reason"] = self._data._client.arrive_delay.reason
        elif self._sensor_type == "CLOSURE":
            self._state = self._data._client.closure.status
            self._attrs["begin"] = self._data._client.closure.begin
            self._attrs["end"] = self._data._client.closure.end
            self._attrs["reason"] = self._data._client.closure.reason
