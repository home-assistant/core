"""
Get WHOIS information for a given host.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.whois/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pythonwhois==2.4.3']

_LOGGER = logging.getLogger(__name__)

CONF_DOMAIN = 'domain'

DEFAULT_NAME = 'Whois'

ATTR_NAME_SERVERS = 'name_servers'
ATTR_REGISTRAR = 'registrar'
ATTR_UPDATED = 'updated'
ATTR_EXPIRES = 'expires'

SCAN_INTERVAL = timedelta(hours=24)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DOMAIN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the WHOIS sensor."""
    from pythonwhois import get_whois
    from pythonwhois.shared import WhoisException

    domain = config.get(CONF_DOMAIN)
    name = config.get(CONF_NAME)

    try:
        if 'expiration_date' in get_whois(domain, normalized=True):
            add_devices([WhoisSensor(name, domain)], True)
        else:
            _LOGGER.error(
                "WHOIS lookup for %s didn't contain expiration_date",
                domain)
            return
    except WhoisException as ex:
        _LOGGER.error(
            "Exception %s occurred during WHOIS lookup for %s", ex, domain)
        return


class WhoisSensor(Entity):
    """Implementation of a WHOIS sensor."""

    def __init__(self, name, domain):
        """Initialize the sensor."""
        from pythonwhois import get_whois

        self.whois = get_whois

        self._name = name
        self._domain = domain

        self._state = None
        self._attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """The icon to represent this sensor."""
        return 'mdi:calendar-clock'

    @property
    def unit_of_measurement(self):
        """The unit of measurement to present the value in."""
        return 'days'

    @property
    def state(self):
        """Return the expiration days for hostname."""
        return self._state

    @property
    def device_state_attributes(self):
        """Get the more info attributes."""
        return self._attributes

    def _empty_state_and_attributes(self):
        """Empty the state and attributes on an error."""
        self._state = None
        self._attributes = None

    def update(self):
        """Get the current WHOIS data for the domain."""
        from pythonwhois.shared import WhoisException

        try:
            response = self.whois(self._domain, normalized=True)
        except WhoisException as ex:
            _LOGGER.error("Exception %s occurred during WHOIS lookup", ex)
            self._empty_state_and_attributes()
            return

        if response:
            if 'expiration_date' not in response:
                _LOGGER.error(
                    "Failed to find expiration_date in whois lookup response. "
                    "Did find: %s", ', '.join(response.keys()))
                self._empty_state_and_attributes()
                return

            if not response['expiration_date']:
                _LOGGER.error("Whois response contains empty expiration_date")
                self._empty_state_and_attributes()
                return

            attrs = {}

            expiration_date = response['expiration_date'][0]
            attrs[ATTR_EXPIRES] = expiration_date.isoformat()

            if 'nameservers' in response:
                attrs[ATTR_NAME_SERVERS] = ' '.join(response['nameservers'])

            if 'updated_date' in response:
                attrs[ATTR_UPDATED] = response['updated_date'][0].isoformat()

            if 'registrar' in response:
                attrs[ATTR_REGISTRAR] = response['registrar'][0]

            time_delta = (expiration_date - expiration_date.now())

            self._attributes = attrs
            self._state = time_delta.days
