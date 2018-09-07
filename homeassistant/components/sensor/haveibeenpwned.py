"""
Support for haveibeenpwned (email breaches) sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.haveibeenpwned/
"""
from datetime import timedelta
import logging

from aiohttp.hdrs import USER_AGENT
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_EMAIL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_point_in_time
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DATE_STR_FORMAT = "%Y-%m-%d %H:%M:%S"

HA_USER_AGENT = "Home Assistant HaveIBeenPwned Sensor Component"

MIN_TIME_BETWEEN_FORCED_UPDATES = timedelta(seconds=5)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

URL = 'https://haveibeenpwned.com/api/v2/breachedaccount/'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HaveIBeenPwned sensor."""
    emails = config.get(CONF_EMAIL)
    data = HaveIBeenPwnedData(emails)

    devices = []
    for email in emails:
        devices.append(HaveIBeenPwnedSensor(data, hass, email))

    add_entities(devices)

    # To make sure we get initial data for the sensors ignoring the normal
    # throttle of 15 minutes but using an update throttle of 5 seconds
    for sensor in devices:
        sensor.update_nothrottle()


class HaveIBeenPwnedSensor(Entity):
    """Implementation of a HaveIBeenPwned sensor."""

    def __init__(self, data, hass, email):
        """Initialize the HaveIBeenPwned sensor."""
        self._state = None
        self._data = data
        self._hass = hass
        self._email = email
        self._unit_of_measurement = "Breaches"

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
        return self._state

    @property
    def device_state_attributes(self):
        """Return the attributes of the sensor."""
        val = {}
        if self._email not in self._data.data:
            return val

        for idx, value in enumerate(self._data.data[self._email]):
            tmpname = "breach {}".format(idx+1)
            tmpvalue = "{} {}".format(
                value["Title"],
                dt_util.as_local(dt_util.parse_datetime(
                    value["AddedDate"])).strftime(DATE_STR_FORMAT))
            val[tmpname] = tmpvalue

        return val

    def update_nothrottle(self, dummy=None):
        """Update sensor without throttle."""
        self._data.update_no_throttle()

        # Schedule a forced update 5 seconds in the future if the update above
        # returned no data for this sensors email. This is mainly to make sure
        # that we don't get HTTP Error "too many requests" and to have initial
        # data after hass startup once we have the data it will update as
        # normal using update
        if self._email not in self._data.data:
            track_point_in_time(
                self._hass, self.update_nothrottle,
                dt_util.now() + MIN_TIME_BETWEEN_FORCED_UPDATES)
            return

        if self._email in self._data.data:
            self._state = len(self._data.data[self._email])
            self.schedule_update_ha_state()

    def update(self):
        """Update data and see if it contains data for our email."""
        self._data.update()

        if self._email in self._data.data:
            self._state = len(self._data.data[self._email])


class HaveIBeenPwnedData:
    """Class for handling the data retrieval."""

    def __init__(self, emails):
        """Initialize the data object."""
        self._email_count = len(emails)
        self._current_index = 0
        self.data = {}
        self._email = emails[0]
        self._emails = emails

    def set_next_email(self):
        """Set the next email to be looked up."""
        self._current_index = (self._current_index + 1) % self._email_count
        self._email = self._emails[self._current_index]

    def update_no_throttle(self):
        """Get the data for a specific email."""
        self.update(no_throttle=True)

    @Throttle(MIN_TIME_BETWEEN_UPDATES, MIN_TIME_BETWEEN_FORCED_UPDATES)
    def update(self, **kwargs):
        """Get the latest data for current email from REST service."""
        try:
            url = "{}{}".format(URL, self._email)

            _LOGGER.debug("Checking for breaches for email: %s", self._email)

            req = requests.get(
                url, headers={USER_AGENT: HA_USER_AGENT}, allow_redirects=True,
                timeout=5)

        except requests.exceptions.RequestException:
            _LOGGER.error("Failed fetching data for %s", self._email)
            return

        if req.status_code == 200:
            self.data[self._email] = sorted(req.json(),
                                            key=lambda k: k["AddedDate"],
                                            reverse=True)

            # Only goto next email if we had data so that
            # the forced updates try this current email again
            self.set_next_email()

        elif req.status_code == 404:
            self.data[self._email] = []

            # only goto next email if we had data so that
            # the forced updates try this current email again
            self.set_next_email()

        else:
            _LOGGER.error("Failed fetching data for %s"
                          "(HTTP Status_code = %d)", self._email,
                          req.status_code)
