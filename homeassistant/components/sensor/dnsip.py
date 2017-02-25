"""
Get your own public IP address or that of any host.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dnsip/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['dnspython==1.15.0']

_LOGGER = logging.getLogger(__name__)

CONF_HOSTNAME = 'hostname'
CONF_RESOLVER = 'resolver'
CONF_RESOLVER_IPV6 = 'resolver_ipv6'
CONF_IPV6 = 'ipv6'

DEFAULT_HOSTNAME = 'myip.opendns.com'
DEFAULT_RESOLVER = '208.67.222.222'
DEFAULT_RESOLVER_IPV6 = '2620:0:ccc::2'
DEFAULT_IPV6 = False

SCAN_INTERVAL = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOSTNAME, default=DEFAULT_HOSTNAME): cv.string,
    vol.Optional(CONF_RESOLVER, default=DEFAULT_RESOLVER): cv.string,
    vol.Optional(CONF_RESOLVER_IPV6, default=DEFAULT_RESOLVER_IPV6): cv.string,
    vol.Optional(CONF_IPV6, default=DEFAULT_IPV6): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the DNS IP sensor."""
    hostname = config.get(CONF_HOSTNAME)
    ipv6 = config.get(CONF_IPV6)
    if ipv6:
        resolver = config.get(CONF_RESOLVER_IPV6)
    else:
        resolver = config.get(CONF_RESOLVER)

    add_devices([WanIpSensor(hostname, resolver, ipv6)])


class WanIpSensor(Entity):
    """Implementation of a DNS IP sensor."""

    def __init__(self, hostname, resolver, ipv6):
        """Initialize the sensor."""
        import dns.resolver
        self._name = hostname
        self.resolver = dns.resolver.Resolver()
        self.resolver.nameservers = [resolver]
        self.querytype = 'aaaa' if ipv6 else 'a'
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the current DNS IP address for hostname."""
        return self._state

    def update(self):
        """Get the current DNS IP address for hostname."""
        response = self.resolver.query(self._name, self.querytype)
        if response:
            self._state = \
                response.response.answer[0].to_rdataset().items[0].address
        else:
            self._state = STATE_UNKNOWN
