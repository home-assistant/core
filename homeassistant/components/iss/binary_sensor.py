"""Support for International Space Station data sensor."""
from datetime import timedelta
import logging

import pyiss
import requests
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_NAME,
    CONF_SHOW_ON_MAP,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_ISS_NEXT_RISE = "next_rise"
ATTR_ISS_NUMBER_PEOPLE_SPACE = "number_of_people_in_space"

DEFAULT_NAME = "ISS"
DEFAULT_DEVICE_CLASS = "visible"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ISS sensor."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    try:
        iss_data = IssData(hass.config.latitude, hass.config.longitude)
        iss_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    name = config.get(CONF_NAME)
    show_on_map = config.get(CONF_SHOW_ON_MAP)

    add_entities([IssBinarySensor(iss_data, name, show_on_map)], True)


class IssBinarySensor(BinarySensorEntity):
    """Implementation of the ISS binary sensor."""

    def __init__(self, iss_data, name, show):
        """Initialize the sensor."""
        self.iss_data = iss_data
        self._state = None
        self._name = name
        self._show_on_map = show

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.iss_data.is_above if self.iss_data else False

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEFAULT_DEVICE_CLASS

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.iss_data:
            attrs = {
                ATTR_ISS_NUMBER_PEOPLE_SPACE: self.iss_data.number_of_people_in_space,
                ATTR_ISS_NEXT_RISE: self.iss_data.next_rise,
            }
            if self._show_on_map:
                attrs[ATTR_LONGITUDE] = self.iss_data.position.get("longitude")
                attrs[ATTR_LATITUDE] = self.iss_data.position.get("latitude")
            else:
                attrs["long"] = self.iss_data.position.get("longitude")
                attrs["lat"] = self.iss_data.position.get("latitude")
            return attrs

    def update(self):
        """Get the latest data from ISS API and updates the states."""
        self.iss_data.update()


class IssData:
    """Get data from the ISS API."""

    def __init__(self, latitude, longitude):
        """Initialize the data object."""
        self.is_above = None
        self.next_rise = None
        self.number_of_people_in_space = None
        self.position = None
        self.latitude = latitude
        self.longitude = longitude

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the ISS API."""
        try:
            iss = pyiss.ISS()
            self.is_above = iss.is_ISS_above(self.latitude, self.longitude)
            self.next_rise = iss.next_rise(self.latitude, self.longitude)
            self.number_of_people_in_space = iss.number_of_people_in_space()
            self.position = iss.current_location()
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
            _LOGGER.error("Unable to retrieve data")
            return False
