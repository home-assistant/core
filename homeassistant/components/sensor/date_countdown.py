"""
Date Countdown
For more details about this sensor please refer to the documentation at
https://home-assistant.io/components/sensor.date_countdown/
"""

import datetime
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle


_LOGGER = logging.getLogger(__name__)

ATTR_DAYS = 'days'
ATTR_HOURS = 'hours'
ATTR_MINUTES = 'minutes'

DEFAULT_NAME = "Countdown"
CONF_DATE = 'date'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DATE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up date countdown sensor."""
    end_date = config.get(CONF_DATE)
    sensor_name = config.get(CONF_NAME)

    add_devices([Countdown(sensor_name, end_date)])


class Countdown(Entity):
    """Implementation of the date countdown sensor."""

    def __init__(self, sensor_name, end_date):
        """Initialize the sensor."""
        self.end_date = end_date
        self._name = sensor_name
        self._state = None
        self._data = {}
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        return {
            ATTR_DAYS: self._data.get("days"),
            ATTR_HOURS: self._data.get("hours"),
            ATTR_MINUTES: self._data.get("minutes")
        }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:calendar'

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Calculate time until end"""
        end_date = datetime.datetime.strptime(self.end_date, '%d-%m-%Y %H:%M')
        days = (end_date - datetime.datetime.now())

        days, seconds = days.days, days.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60

        self._data["days"] = days
        self._data["hours"] = hours
        self._data["minutes"] = minutes

        self._state = str(days) + " days " + str(hours) \
            + " hours " + str(minutes) + " minutes"
