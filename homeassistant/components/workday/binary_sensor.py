"""Sensor to indicate whether the current day is a workday."""
import logging
from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, WEEKDAYS
from homeassistant.components.binary_sensor import BinarySensorDevice
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# List of all countries currently supported by holidays
# There seems to be no way to get the list out at runtime
ALL_COUNTRIES = [
    'Argentina', 'AR', 'Australia', 'AU', 'Austria', 'AT',
    'Brazil', 'BR', 'Belarus', 'BY', 'Belgium', 'BE', 'Bulgaria', 'BG',
    'Canada', 'CA', 'Colombia', 'CO', 'Croatia', 'HR', 'Czech', 'CZ',
    'Denmark', 'DK',
    'England', 'EuropeanCentralBank', 'ECB', 'TAR',
    'Finland', 'FI', 'France', 'FRA',
    'Germany', 'DE',
    'Hungary', 'HU', 'Honduras', 'HUD',
    'India', 'IND', 'Ireland', 'IE', 'Isle of Man', 'Italy', 'IT',
    'Japan', 'JP',
    'Lithuania', 'LT', 'Luxembourg', 'LU',
    'Mexico', 'MX',
    'Netherlands', 'NL', 'NewZealand', 'NZ', 'Northern Ireland',
    'Norway', 'NO',
    'Polish', 'PL', 'Portugal', 'PT', 'PortugalExt', 'PTE',
    'Russia', 'RU',
    'Scotland', 'Slovenia', 'SI', 'Slovakia', 'SK',
    'South Africa', 'ZA', 'Spain', 'ES', 'Sweden', 'SE', 'Switzerland', 'CH',
    'Ukraine', 'UA', 'UnitedKingdom', 'UK', 'UnitedStates', 'US', 'Wales',
]

ALLOWED_DAYS = WEEKDAYS + ['holiday']

CONF_COUNTRY = 'country'
CONF_PROVINCE = 'province'
CONF_WORKDAYS = 'workdays'
CONF_EXCLUDES = 'excludes'
CONF_OFFSET = 'days_offset'
CONF_ADD_HOLIDAYS = 'add_holidays'

# By default, Monday - Friday are workdays
DEFAULT_WORKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri']
# By default, public holidays, Saturdays and Sundays are excluded from workdays
DEFAULT_EXCLUDES = ['sat', 'sun', 'holiday']
DEFAULT_NAME = 'Workday Sensor'
DEFAULT_OFFSET = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COUNTRY): vol.In(ALL_COUNTRIES),
    vol.Optional(CONF_EXCLUDES, default=DEFAULT_EXCLUDES):
        vol.All(cv.ensure_list, [vol.In(ALLOWED_DAYS)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OFFSET, default=DEFAULT_OFFSET): vol.Coerce(int),
    vol.Optional(CONF_PROVINCE): cv.string,
    vol.Optional(CONF_WORKDAYS, default=DEFAULT_WORKDAYS):
        vol.All(cv.ensure_list, [vol.In(ALLOWED_DAYS)]),
    vol.Optional(CONF_ADD_HOLIDAYS): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Workday sensor."""
    import holidays

    sensor_name = config.get(CONF_NAME)
    country = config.get(CONF_COUNTRY)
    province = config.get(CONF_PROVINCE)
    workdays = config.get(CONF_WORKDAYS)
    excludes = config.get(CONF_EXCLUDES)
    days_offset = config.get(CONF_OFFSET)
    add_holidays = config.get(CONF_ADD_HOLIDAYS)

    year = (get_date(datetime.today()) + timedelta(days=days_offset)).year
    obj_holidays = getattr(holidays, country)(years=year)

    if province:
        # 'state' and 'prov' are not interchangeable, so need to make
        # sure we use the right one
        if (hasattr(obj_holidays, 'PROVINCES') and
                province in obj_holidays.PROVINCES):
            obj_holidays = getattr(holidays, country)(
                prov=province, years=year)
        elif (hasattr(obj_holidays, 'STATES') and
              province in obj_holidays.STATES):
            obj_holidays = getattr(holidays, country)(
                state=province, years=year)
        else:
            _LOGGER.error("There is no province/state %s in country %s",
                          province, country)
            return

    # Add custom holidays
    try:
        obj_holidays.append(add_holidays)
    except TypeError:
        _LOGGER.debug("No custom holidays or invalid holidays")

    _LOGGER.debug("Found the following holidays for your configuration:")
    for date, name in sorted(obj_holidays.items()):
        _LOGGER.debug("%s %s", date, name)

    add_entities([IsWorkdaySensor(
        obj_holidays, workdays, excludes, days_offset, sensor_name)], True)


def day_to_string(day):
    """Convert day index 0 - 7 to string."""
    try:
        return ALLOWED_DAYS[day]
    except IndexError:
        return None


def get_date(date):
    """Return date. Needed for testing."""
    return date


class IsWorkdaySensor(BinarySensorDevice):
    """Implementation of a Workday sensor."""

    def __init__(self, obj_holidays, workdays, excludes, days_offset, name):
        """Initialize the Workday sensor."""
        self._name = name
        self._obj_holidays = obj_holidays
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
        if 'holiday' in self._workdays and now in self._obj_holidays:
            return True

        return False

    def is_exclude(self, day, now):
        """Check if given day is in the excludes list."""
        if day in self._excludes:
            return True
        if 'holiday' in self._excludes and now in self._obj_holidays:
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

    async def async_update(self):
        """Get date and look whether it is a holiday."""
        # Default is no workday
        self._state = False

        # Get iso day of the week (1 = Monday, 7 = Sunday)
        date = get_date(datetime.today()) + timedelta(days=self._days_offset)
        day = date.isoweekday() - 1
        day_of_week = day_to_string(day)

        if self.is_include(day_of_week, date):
            self._state = True

        if self.is_exclude(day_of_week, date):
            self._state = False
