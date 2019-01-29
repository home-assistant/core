"""
Support for Linky.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.linky/
"""
import logging
import json
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT,
                                 STATE_UNAVAILABLE, CONF_NAME)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pylinky==0.1.8']

KILOWATT_HOUR = 'kWh'

DEFAULT_NAME = 'Linky'

PEAK_HOURS = 'peak_hours'
PEAK_HOURS_COST = 'peak_hours_cost'
OFFPEAK_HOURS_COST = 'offpeak_hours_cost'

CONSUMPTION = "conso"
TIME = "time"

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)
SCAN_INTERVAL = timedelta(minutes=30)
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(PEAK_HOURS): vol.All(cv.ensure_list),
    vol.Required(PEAK_HOURS_COST): vol.Coerce(float),
    vol.Required(OFFPEAK_HOURS_COST): vol.Coerce(float),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Linky sensor."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    timeout = config.get(CONF_TIMEOUT)
    name = config.get(CONF_NAME)
    peak_hours = config.get(PEAK_HOURS)
    peak_hours_cost = config.get(PEAK_HOURS_COST)
    offpeak_hours_cost = config.get(OFFPEAK_HOURS_COST)

    linky_data = LinkyData(username, password, timeout)

    add_entities([LinkySensor(name, linky_data, peak_hours,
                              peak_hours_cost, offpeak_hours_cost)])
    return True


class LinkySensor(Entity):
    """Representation of a sensor entity for Linky."""

    def __init__(self, name, linky_data,
                 peak_hours, peak_hours_cost,
                 offpeak_hours_cost):
        """Initialize the sensor."""
        self._name = name
        self._peak_hours = peak_hours
        self._peak_hours_cost = peak_hours_cost
        self._offpeak_hours_cost = offpeak_hours_cost
        self._unit = KILOWATT_HOUR
        self._icon = "mdi:flash"
        self._lk = linky_data
        self._state = None
        self._attributes = {}
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Fetch new state data for the sensor.
        """
        _LOGGER.debug("Start of update of linky data")
        self._lk.update()
        if not self._lk.success:
            self._state = STATE_UNAVAILABLE
            self._attributes = []
            return

        self._state = self._lk.daily[1][CONSUMPTION]
        self._attributes["halfhourly"] = [d[CONSUMPTION]
                                          for d in self._lk.halfhourly]
        self._attributes["daily"] = [d[CONSUMPTION]
                                     for d in self._lk.daily]
        self._attributes["peak_hours"] = sum([
            d[CONSUMPTION]
            if any([between(h[0], h[1], d[TIME])
                    for h in self._peak_hours])
            else 0 for d in self._lk.halfhourly]) / 2
        # From kW for 30 minutes to kWh
        self._attributes["offpeak_hours"] = sum(
            [0 if any([between(h[0], h[1], d[TIME])
                       for h in self._peak_hours])
             else d[CONSUMPTION]
             for d in self._lk.halfhourly]) / 2
        # From kW for 30 minutes to kWh
        self._attributes["peak_offpeak_percent"] = ((self._attributes
                                                    ["peak_hours"] *
                                                    100) /
                                                    (self._attributes["peak_hours"] +
         self._attributes["offpeak_hours"]))
        self._attributes["daily_cost"] = (self._peak_hours_cost * 
                                          self._attributes["peak_hours"] +
                                          self._offpeak_hours_cost *
                                          self._attributes["offpeak_hours"])
        self._attributes["monthly_evolution"] = (
            1 - ((self._lk.monthly[0][CONSUMPTION]) /
                 (self._lk.compare_month))) * 100
        _LOGGER.debug("Computed values: " +
                      str(self._attributes))


def hour_to_min(hour):
    return sum(map(lambda x, y: int(x)*y, hour.split(":"), [60, 1]))


def between(start, end, hour):
    min_start = hour_to_min(start)
    min_end = hour_to_min(end)
    min_hour = hour_to_min(hour)
    return (min_start <= min_hour <= min_end
            if min_start < min_end
            else min_start >= min_hour >= min_end)


class LinkyData:
    """The class for handling the data retrieval."""

    def __init__(self, username, password, timeout):
        """Initialize the data object."""
        self._username = username
        self._password = password
        self._timeout = timeout
        self.client = {}
        self.data = {}
        self.success = False

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _fetch_data(self):
        """Fetch latest data from Linky."""
        from pylinky.client import PyLinkyError
        from pylinky import LinkyClient
        from datetime import date
        from dateutil.relativedelta import relativedelta
        try:
            self.client = LinkyClient(self._username, self._password,
                                      None, self._timeout)
            self.client.fetch_data()
            _LOGGER.info("Connected to Enedis server successfully.")
            self.data = self.client.get_data()
            today = date.today()
            # Fixes a bug in PyLinky
            self.data["monthly"][0] = (self.client._get_data_per_month(
                (today.replace(day=1) - relativedelta(months=12))
                .strftime("%d/%m/%Y"),
                ((today - relativedelta(months=11)).replace(day=1)
                 - relativedelta(days=1)).strftime("%d/%m/%Y"))[0])
            _LOGGER.info("Second request for bugfix")
            # Get partial CONSUMPTION of the same month last year
            self.compare_month = sum([d[CONSUMPTION]
                                      for d in self.client
                                      ._get_data_per_month(
                                          (today.replace(day=1) -
                                           relativedelta(months=12))
                                          .strftime("%d/%m/%Y"),
                                          (today - relativedelta
                                           (months=12))
                                          .strftime("%d/%m/%Y"))])
            _LOGGER.info("Same month last year " +
                         "(from 1st to same day): " +
                         str(self.compare_month))
        except PyLinkyError as exp:
            _LOGGER.warning("Unable to fetch Linky data " +
                            "(maybe due to night maintenance " +
                            "downtime schedule): %s", exp)
            return False
        return True

    def update(self):
        """Return the latest collected data from Linky."""
        self._fetch_data()
        if not self.data:
            return
        _LOGGER.debug("Linky data retrieved: " + str(self.data))
        self.halfhourly = list(reversed(self.data["hourly"]))
        self.daily = list(reversed(self.data["daily"]))
        self.monthly = list(reversed(self.data["monthly"]))
        self.yearly = list(reversed(self.data["yearly"]))
        self.success = True
