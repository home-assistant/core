"""
Sensor to indicate whether the current day is a workday base on workalendar module.
The code is based on binary_sensor.workday home-assistant component

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.workday/
"""
import asyncio
import importlib
import logging
from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, WEEKDAYS
from homeassistant.components.binary_sensor import BinarySensorDevice
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['workalendar==2.3.1']

CONF_COUNTRY = 'country'
CONF_WORKDAYS = 'workdays'
# By default, Monday - Friday are workdays
DEFAULT_WORKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri']
CONF_EXCLUDES = 'excludes'
# By default, public holidays, Saturdays and Sundays are excluded from workdays
DEFAULT_EXCLUDES = ['sat', 'sun', 'holiday']
DEFAULT_NAME = 'Workday Sensor'
ALLOWED_DAYS = WEEKDAYS + ['holiday']
CONF_OFFSET = 'days_offset'
DEFAULT_OFFSET = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COUNTRY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OFFSET, default=DEFAULT_OFFSET): vol.Coerce(int),
    vol.Optional(CONF_WORKDAYS, default=DEFAULT_WORKDAYS):
        vol.All(cv.ensure_list, [vol.In(ALLOWED_DAYS)]),
    vol.Optional(CONF_EXCLUDES, default=DEFAULT_EXCLUDES):
        vol.All(cv.ensure_list, [vol.In(ALLOWED_DAYS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Workday sensor."""

    sensor_name = config.get(CONF_NAME)
    country = config.get(CONF_COUNTRY)
    workdays = config.get(CONF_WORKDAYS)
    excludes = config.get(CONF_EXCLUDES)
    days_offset = config.get(CONF_OFFSET)

    year = (datetime.now() + timedelta(days=days_offset)).year
    components = country.split('.')

    if len(components) != 2:
        _LOGGER.error('You must specify a continent and a country in the form continent.Country')
        return False

    try:
        workalendar = importlib.import_module('workalendar.' + components[0])
    except TypeError:
        _LOGGER.error('You must specify a continent supported in workalendar')
        return False
    except ImportError:
        return False

    if not hasattr(workalendar, components[1]):
        _LOGGER.error('You must specify a country supported in workalendar')
        return False

    calendar = getattr(workalendar, components[1])()
    _LOGGER.debug("Found the following holidays for your configuration:")
    for date, name in sorted(calendar.holidays(year)):
        _LOGGER.debug("%s %s", date, name)

    add_devices([IsWorkdaySensor(
        calendar, workdays, excludes, days_offset, sensor_name)], True)


def day_to_string(day):
    """Convert day index 0 - 7 to string."""
    try:
        return ALLOWED_DAYS[day]
    except IndexError:
        return None


class IsWorkdaySensor(BinarySensorDevice):
    """Implementation of a Workday sensor."""

    def __init__(self, calendar, workdays, excludes, days_offset, name):
        """Initialize the Workday sensor."""
        self._name = name
        self.calendar = calendar
        self._workdays = workdays
        self._excludes = excludes
        self._days_offset = days_offset
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the device."""
        return self._state

    def is_include(self, day, now):
        """Check if given day is in the includes list."""
        if day in self._workdays:
            return True
        elif 'holiday' in self._workdays and not self.calendar.is_working_day(now):
            return True

        return False

    def is_exclude(self, day, now):
        """Check if given day is in the excludes list."""
        if day in self._excludes:
            return True
        elif 'holiday' in self._excludes and not self.calendar.is_working_day(now):
            return True

        return False

    @property
    def state_attributes(self):
        """Return the attributes of the entity."""
        # return self._attributes
        return {
            CONF_WORKDAYS: self._workdays,
            CONF_EXCLUDES: self._excludes,
            CONF_OFFSET: self._days_offset
        }

    @asyncio.coroutine
    def async_update(self):
        """Get date and look whether it is a holiday."""
        # Default is no workday
        self._state = False

        # Get iso day of the week (1 = Monday, 7 = Sunday)
        date = datetime.today() + timedelta(days=self._days_offset)
        day = date.isoweekday() - 1
        day_of_week = day_to_string(day)

        if self.is_include(day_of_week, date):
            self._state = True

        if self.is_exclude(day_of_week, date):
            self._state = False

