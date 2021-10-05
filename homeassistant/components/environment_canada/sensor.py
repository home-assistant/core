"""Support for the Environment Canada weather service."""
from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LOCATION,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(minutes=10)

ATTR_UPDATED = "updated"
ATTR_STATION = "station"
ATTR_TIME = "alert time"

CONF_ATTRIBUTION = "Data provided by Environment Canada"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["weather_coordinator"]
    sensor_list = list(coordinator.conditions) + list(coordinator.alerts)
    async_add_entities(
        [ECSensor(sensor_type, coordinator) for sensor_type in sensor_list], True
    )


class ECSensor(SensorEntity):
    """Implementation of an Environment Canada sensor."""

    def __init__(self, sensor_type, ec_data):
        """Initialize the sensor."""
        self.sensor_type = sensor_type
        self.ec_data = ec_data

        self._unique_id = None
        self._name = None
        self._state = None
        self._attr = None
        self._unit = None
        self._device_class = None

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attr

    @property
    def native_unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    async def async_update(self):
        """Update current conditions."""
        await self.hass.async_add_executor_job(self.ec_data.update)
        self.ec_data.conditions.update(self.ec_data.alerts)

        conditions = self.ec_data.conditions
        metadata = self.ec_data.metadata
        sensor_data = conditions.get(self.sensor_type)

        self._unique_id = f"{metadata['location']}-{self.sensor_type}"
        self._attr = {}
        self._name = sensor_data.get("label")
        value = sensor_data.get("value")

        if isinstance(value, list):
            self._state = " | ".join([str(s.get("title")) for s in value])[:255]
            self._attr.update(
                {ATTR_TIME: " | ".join([str(s.get("date")) for s in value])}
            )
        elif self.sensor_type == "tendency":
            self._state = str(value).capitalize()
        elif value is not None and len(value) > 255:
            self._state = value[:255]
            _LOGGER.info("Value for %s truncated to 255 characters", self._unique_id)
        else:
            self._state = value

        if sensor_data.get("unit") == "C" or self.sensor_type in (
            "wind_chill",
            "humidex",
        ):
            self._unit = TEMP_CELSIUS
            self._device_class = DEVICE_CLASS_TEMPERATURE
        else:
            self._unit = sensor_data.get("unit")

        timestamp = metadata.get("timestamp")
        if timestamp:
            updated_utc = datetime.strptime(timestamp, "%Y%m%d%H%M%S").isoformat()
        else:
            updated_utc = None

        self._attr.update(
            {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_UPDATED: updated_utc,
                ATTR_LOCATION: metadata.get("location"),
                ATTR_STATION: metadata.get("station"),
            }
        )
