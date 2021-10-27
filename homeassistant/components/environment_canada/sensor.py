"""Support for the Environment Canada weather service."""
import logging
import re

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_LOCATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import trigger_import
from .const import (
    ATTR_OBSERVATION_TIME,
    ATTR_STATION,
    CONF_LANGUAGE,
    CONF_STATION,
    DOMAIN,
)

ATTR_TIME = "alert time"

_LOGGER = logging.getLogger(__name__)


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return None
    if not re.fullmatch(r"[A-Z]{2}/s0000\d{3}", station):
        raise vol.Invalid('Station ID must be of the form "XX/s0000###"')
    return station


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_LANGUAGE, default="english"): vol.In(["english", "french"]),
        vol.Optional(CONF_STATION): validate_station,
        vol.Inclusive(CONF_LATITUDE, "latlon"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "latlon"): cv.longitude,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Environment Canada sensor."""
    trigger_import(hass, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["weather_coordinator"]
    weather_data = coordinator.ec_data

    sensors = list(weather_data.conditions)
    labels = [weather_data.conditions[sensor]["label"] for sensor in sensors]
    alerts_list = list(weather_data.alerts)
    labels = labels + [weather_data.alerts[sensor]["label"] for sensor in alerts_list]
    sensors = sensors + alerts_list

    async_add_entities(
        [
            ECSensor(coordinator, sensor, label)
            for sensor, label in zip(sensors, labels)
        ],
        True,
    )


class ECSensor(CoordinatorEntity, SensorEntity):
    """Implementation of an Environment Canada sensor."""

    def __init__(self, coordinator, sensor, label):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.sensor_type = sensor
        self.ec_data = coordinator.ec_data

        self._attr_attribution = self.ec_data.metadata["attribution"]
        self._attr_name = f"{coordinator.config_entry.title} {label}"
        self._attr_unique_id = f"{self.ec_data.metadata['location']}-{sensor}"
        self._attr = None
        self._unit = None
        self._device_class = None

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

    @property
    def native_value(self):
        """Update current conditions."""
        metadata = self.ec_data.metadata
        sensor_data = self.ec_data.conditions.get(self.sensor_type)
        if not sensor_data:
            sensor_data = self.ec_data.alerts.get(self.sensor_type)

        self._attr = {}
        value = sensor_data.get("value")

        if isinstance(value, list):
            state = " | ".join([str(s.get("title")) for s in value])[:255]
            self._attr.update(
                {ATTR_TIME: " | ".join([str(s.get("date")) for s in value])}
            )
        elif self.sensor_type == "tendency":
            state = str(value).capitalize()
        elif isinstance(value, str) and len(value) > 255:
            state = value[:255]
            _LOGGER.info(
                "Value for %s truncated to 255 characters", self._attr_unique_id
            )
        else:
            state = value

        if sensor_data.get("unit") == "C" or self.sensor_type in (
            "wind_chill",
            "humidex",
        ):
            self._unit = TEMP_CELSIUS
            self._device_class = DEVICE_CLASS_TEMPERATURE
        else:
            self._unit = sensor_data.get("unit")

        self._attr.update(
            {
                ATTR_OBSERVATION_TIME: metadata.get("timestamp"),
                ATTR_LOCATION: metadata.get("location"),
                ATTR_STATION: metadata.get("station"),
            }
        )
        return state
