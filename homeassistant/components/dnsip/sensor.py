"""Get your own public IP address or that of any host."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_HOSTNAME = 'hostname'
CONF_IPV6 = 'ipv6'
CONF_RESOLVER = 'resolver'
CONF_RESOLVER_IPV6 = 'resolver_ipv6'

DEFAULT_HOSTNAME = 'myip.opendns.com'
DEFAULT_IPV6 = False
DEFAULT_NAME = 'myip'
DEFAULT_RESOLVER = '208.67.222.222'
DEFAULT_RESOLVER_IPV6 = '2620:0:ccc::2'

SCAN_INTERVAL = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_HOSTNAME, default=DEFAULT_HOSTNAME): cv.string,
    vol.Optional(CONF_RESOLVER, default=DEFAULT_RESOLVER): cv.string,
    vol.Optional(CONF_RESOLVER_IPV6, default=DEFAULT_RESOLVER_IPV6): cv.string,
    vol.Optional(CONF_IPV6, default=DEFAULT_IPV6): cv.boolean,
})


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the DNS IP sensor."""
    hostname = config.get(CONF_HOSTNAME)
    name = config.get(CONF_NAME)
    if not name:
        if hostname == DEFAULT_HOSTNAME:
            name = DEFAULT_NAME
        else:
            name = hostname
    ipv6 = config.get(CONF_IPV6)
    if ipv6:
        resolver = config.get(CONF_RESOLVER_IPV6)
    else:
        resolver = config.get(CONF_RESOLVER)

    async_add_devices([WanIpSensor(
        hass, name, hostname, resolver, ipv6)], True)


class WanIpSensor(Entity):
    """Implementation of a DNS IP sensor."""

    def __init__(self, hass, name, hostname, resolver, ipv6):
        """Initialize the DNS IP sensor."""
        import aiodns

        self.hass = hass
        self._name = name
        self.hostname = hostname
        self.resolver = aiodns.DNSResolver(loop=self.hass.loop)
        self.resolver.nameservers = [resolver]
        self.querytype = 'AAAA' if ipv6 else 'A'
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the current DNS IP address for hostname."""
        return self._state

    async def async_update(self):
        """Get the current DNS IP address for hostname."""
        from aiodns.error import DNSError

        try:
            response = await self.resolver.query(
                self.hostname, self.querytype)
        except DNSError as err:
            _LOGGER.warning("Exception while resolving host: %s", err)
            response = None
        if response:
            self._state = response[0].host
        else:
            self._state = None
