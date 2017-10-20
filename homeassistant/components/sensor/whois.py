"""
Get WHOIS information for a given host.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.whois/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pythonwhois==2.4.3']

_LOGGER = logging.getLogger(__name__)

CONF_HOST = 'hosts'

ATTR_NAME_SERVERS = 'name_servers'
ATTR_REGISTRAR = 'registrar'
ATTR_UPDATED = 'updated'
ATTR_EXPIRES = 'expires'

SCAN_INTERVAL = timedelta(hours=24)  # WHOIS info is very slow moving
# We also want to prevent DOS / TOS breaking; One request per domain
# every 24 hours shouldn't count as "high volume"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_devices, disovery_info=None):
    """Set up the WHOIS sensor."""
    hostnames = config.get(CONF_HOST)

    devices = []

    for hostname in hostnames:
        devices.append(WhoisSensor(hass, hostname))

    add_devices(devices, True)


class WhoisSensor(Entity):
    """Implementation of a WHOIS sensor."""

    def __init__(self, hass, hostname):
        """Initialize the sensor."""
        from pythonwhois import get_whois

        self.hass = hass
        self._hostname = hostname
        self.whois = get_whois
        self._state = STATE_UNKNOWN
        self._data = None
        self._expired = False
        self._expiration_date = None
        self._name_servers = []

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'whois_{}'.format(self._hostname)

    @property
    def icon(self):
        """The icon to represent this sensor."""
        return 'mdi:calendar-clock'

    @property
    def unit_of_measurement(self):
        """The unit of measurement to present the value in."""
        if self._expired:
            return None

        return 'day{}'.format('' if self._state == 1 else 's')

    @property
    def state(self):
        """Return the expiration days for hostname."""
        if self._expired:
            return 'Expired'

        return self._state

    @property
    def device_state_attributes(self):
        """Get the more info attributes."""
        if self._data:
            updated_formatted = self._updated_date.strftime(
                '%Y-%m-%d %H:%M:%S')
            expires_formatted = self._expiration_date.strftime(
                '%Y-%m-%d %H:%M:%S')

            return {
                ATTR_NAME_SERVERS: ' '.join(self._name_servers),
                ATTR_REGISTRAR: self._data['registrar'][0],
                ATTR_UPDATED: updated_formatted,
                ATTR_EXPIRES: expires_formatted,
            }

    def update(self):
        """Get the current WHOIS data for hostname."""
        response = self.whois(self._hostname, normalized=True)

        if response:
            self._data = response

            if self._data['nameservers']:
                self._name_servers = self._data['nameservers']

            self._expiration_date = self._data['expiration_date'][0]
            self._updated_date = self._data['updated_date'][0]

            time_delta = (self._expiration_date - self._expiration_date.now())

            self._state = time_delta.days
            self._expired = self._state <= 0
        else:
            self._state = STATE_UNKNOWN
