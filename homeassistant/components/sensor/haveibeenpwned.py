"""
Support for haveibeenpwned (email breaches) sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.haveibeenpwned/
"""
from datetime import timedelta
import logging

import voluptuous as vol
import requests

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (STATE_UNKNOWN, CONF_EMAIL)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DATE_STR_FORMAT = "%Y-%m-%d %H:%M:%S"
USER_AGENT = "Home Assistant HaveIBeenPwned Sensor Component"

SCAN_INTERVAL = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): vol.All(cv.ensure_list, [cv.string]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the RESTful sensor."""
    emails = config.get(CONF_EMAIL)

    data = HaveIBeenPwnedData(emails)
    data.update = Throttle(timedelta(seconds=SCAN_INTERVAL-1))(data.update)

    dev = []
    for email in emails:
        dev.append(HaveIBeenPwnedSensor(data, email))

    add_devices(dev)


class HaveIBeenPwnedSensor(Entity):
    """Implementation of HaveIBeenPwnedSensor."""

    def __init__(self, data, email):
        """Initialize the HaveIBeenPwnedSensor sensor."""
        self._value = None
        self._data = data
        self._email = email
        self._unit_of_measurement = "Hits"
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Breaches {}".format(self._email)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        if self._value is None:
            return STATE_UNKNOWN
        else:
            return len(self._value)

    @property
    def state_attributes(self):
        """Return the atrributes of the sensor."""
        val = {}
        if self._value is None:
            return val

        for idx, value in enumerate(self._value):
            tmpname = "breach {}".format(idx+1)
            tmpvalue = "{} {}".format(
                value["Title"],
                dt_util.as_local(dt_util.parse_datetime(
                    value["AddedDate"])).strftime(DATE_STR_FORMAT))
            val[tmpname] = tmpvalue

        return val

    def update(self):
        """Get data for (next) email and set value if it's our email."""
        self._data.update()
        if self._data.email == self._email:
            self._value = self._data.data


# pylint: disable=too-few-public-methods
class HaveIBeenPwnedData(object):
    """Class for handling the data retrieval."""

    def __init__(self, emails):
        """Initialize the data object."""
        self._email_count = len(emails)
        self._current_index = -1
        self.data = None
        self.email = None
        self._emails = emails

    def update(self):
        """Get the latest data for current email from REST service."""
        try:
            self.data = None
            self._current_index = (self._current_index + 1) % self._email_count
            self.email = self._emails[self._current_index]
            url = "https://haveibeenpwned.com/api/v2/breachedaccount/{}". \
                format(self.email)

            _LOGGER.info("Checking for breaches for email %s", self.email)

            req = requests.get(url, headers={"User-agent": USER_AGENT},
                               allow_redirects=True, timeout=5)

            # Intial data for all email addresses have been gathered
            # Throttle the amount of requests made to 1 per 15 minutes to
            # prevent abuse and because the data will almost never change.
            # This means the more email addresses that are specified the
            # longer it will take to update them all, this is part of
            # abuse protection. I emailed the owner of the api to see
            # if he was ok with this abuse protection scheme and it
            # was fine for him like this
            if self._current_index == self._email_count - 1:
                global SCAN_INTERVAL
                SCAN_INTERVAL = 60*15
                self.update = Throttle(timedelta(
                    seconds=SCAN_INTERVAL-5))(self.update)

        except requests.exceptions.RequestException as exception:
            _LOGGER.error(exception)
            return

        if req.status_code == 200:
            self.data = sorted(req.json(), key=lambda k: k["AddedDate"],
                               reverse=True)
        elif req.status_code == 404:
            self.data = []
        else:
            _LOGGER.error("failed fetching HaveIBeenPwned Data for '%s'"
                          "(HTTP Status_code = %d)", self.email,
                          req.status_code)
