"""Support for iss binary sensor."""
from __future__ import annotations

from datetime import timedelta
import logging

import pyiss
import requests
from requests.exceptions import HTTPError

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_ISS_NEXT_RISE = "next_rise"
ATTR_ISS_NUMBER_PEOPLE_SPACE = "number_of_people_in_space"

DEFAULT_NAME = "ISS"
DEFAULT_DEVICE_CLASS = "visible"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    name = entry.title
    show_on_map = entry.options.get(CONF_SHOW_ON_MAP, False)

    try:
        iss_data = IssData(hass.config.latitude, hass.config.longitude)
        await hass.async_add_executor_job(iss_data.update)
    except HTTPError as error:
        _LOGGER.error(error)
        return

    async_add_entities([IssBinarySensor(iss_data, name, show_on_map)], True)


class IssBinarySensor(BinarySensorEntity):
    """Implementation of the ISS binary sensor."""

    _attr_device_class = DEFAULT_DEVICE_CLASS

    def __init__(self, iss_data, name, show):
        """Initialize the sensor."""
        self.iss_data = iss_data
        self._state = None
        self._attr_name = name
        self._show_on_map = show

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.iss_data.is_above if self.iss_data else False

    @property
    def extra_state_attributes(self):
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
        except (HTTPError, requests.exceptions.ConnectionError):
            _LOGGER.error("Unable to retrieve data")
            return False
