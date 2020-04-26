"""Support for UK Met Office weather service."""

import logging

import datapoint as dp
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    LENGTH_KILOMETERS,
    PRESSURE_HPA,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_LAST_UPDATE,
    ATTR_SENSOR_ID,
    ATTR_SITE_ID,
    ATTR_SITE_NAME,
    ATTRIBUTION,
    CONDITION_CLASSES,
    DEFAULT_NAME,
    VISIBILITY_CLASSES,
)
from .data import MetOfficeData

_LOGGER = logging.getLogger(__name__)

# Sensor types are defined as: name, units, icon
SENSOR_TYPES = {
    "name": ["Station Name", None, None],
    "weather": ["Weather", None, "mdi:weather-sunny"],  # will adapt to the weather
    "temperature": ["Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "feels_like_temperature": [
        "Feels Like Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "wind_speed": ["Wind Speed", SPEED_MILES_PER_HOUR, "mdi:weather-windy"],
    "wind_direction": ["Wind Direction", None, "mdi:weather-windy"],
    "wind_gust": ["Wind Gust", SPEED_MILES_PER_HOUR, "mdi:weather-windy"],
    "visibility": ["Visibility", LENGTH_KILOMETERS, "mdi:eye"],
    "uv": ["UV Index", None, "mdi:weather-sunny-alert"],
    "precipitation": [
        "Probability of Precipitation",
        UNIT_PERCENTAGE,
        "mdi:weather-rainy",
    ],
    "humidity": ["Humidity", UNIT_PERCENTAGE, "mdi:water-percent"],
    "pressure": ["Pressure", PRESSURE_HPA, "mdi:thermometer"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Met Office sensor platform."""
    _LOGGER.debug("Setting up platform from config: %s", config)

    latitude = config.get(CONF_LATITUDE)
    longitude = config.get(CONF_LONGITUDE)
    name = config.get(CONF_NAME)

    try:
        datapoint = dp.connection(api_key=config.get(CONF_API_KEY))
    except dp.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return

    data = None

    if None in (latitude, longitude):
        _LOGGER.debug("No specific location set in config, tracking HASS settings")
        latitude = hass.config.latitude
        longitude = hass.config.longitude

        def track_core_config_changes(event):
            _LOGGER.debug(
                "Informed of change in core configuration: %s",
                (
                    event.event_type,
                    event.data,
                    event.origin,
                    event.time_fired,
                    event.context,
                ),
            )

            if data is not None:
                _LOGGER.debug("Updating sensor MetOfficeData with new site")
                data.position = (event.data["latitude"], event.data["longitude"])
                data.update()

        hass.bus.listen("core_config_updated", track_core_config_changes)

    else:
        _LOGGER.debug("Specific location set, cannot track config changes")

    data = MetOfficeData(hass, datapoint, (latitude, longitude))
    add_entities(
        [
            MetOfficeCurrentSensor(name, variable, data)
            for variable in config[CONF_MONITORED_CONDITIONS]
        ]
    )


class MetOfficeCurrentSensor(Entity):
    """Implementation of a Met Office current sensor."""

    def __init__(self, name, condition, data):
        """Initialize the sensor."""
        self._name = name
        self._condition = condition
        self.data = data

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {SENSOR_TYPES[self._condition][0]}"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._condition == "visibility":
            return VISIBILITY_CLASSES.get(self.data.now.visibility.value)

        if hasattr(self.data.now, self._condition):
            variable = getattr(self.data.now, self._condition)
            if self._condition == "weather":
                return [
                    k
                    for k, v in CONDITION_CLASSES.items()
                    if self.data.now.weather.value in v
                ][0]
            return variable.value if variable else None
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._condition][1]

    @property
    def icon(self):
        """Return the icon for the entity card."""
        return (
            f"mdi:weather-{self.state}"
            if self._condition == "weather"
            else SENSOR_TYPES[self._condition][2]
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_LAST_UPDATE: self.data.now.date,
            ATTR_SENSOR_ID: self._condition,
            ATTR_SITE_ID: self.data.site.id,
            ATTR_SITE_NAME: self.data.site.name,
        }
        return attr

    def update(self):
        """Update current conditions."""
        self.data.update()
