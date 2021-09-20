"""Get your own public IP address or that of any host."""
from __future__ import annotations

from datetime import timedelta
import logging

import aiodns
from aiodns.error import DNSError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_HOSTNAME = "hostname"
CONF_IPV6 = "ipv6"
CONF_RESOLVER = "resolver"
CONF_RESOLVER_IPV6 = "resolver_ipv6"

DEFAULT_HOSTNAME = "myip.opendns.com"
DEFAULT_IPV6 = False
DEFAULT_NAME = "myip"
DEFAULT_RESOLVER = "208.67.222.222"
DEFAULT_RESOLVER_IPV6 = "2620:0:ccc::2"

SCAN_INTERVAL = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_HOSTNAME, default=DEFAULT_HOSTNAME): cv.string,
        vol.Optional(CONF_RESOLVER, default=DEFAULT_RESOLVER): cv.string,
        vol.Optional(CONF_RESOLVER_IPV6, default=DEFAULT_RESOLVER_IPV6): cv.string,
        vol.Optional(CONF_IPV6, default=DEFAULT_IPV6): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the DNS IP sensor."""
    hostname = config[CONF_HOSTNAME]
    name = config.get(CONF_NAME)
    ipv6 = config[CONF_IPV6]

    if not name:
        name = DEFAULT_NAME if hostname == DEFAULT_HOSTNAME else hostname
    resolver = config[CONF_RESOLVER_IPV6] if ipv6 else config[CONF_RESOLVER]

    async_add_devices([WanIpSensor(name, hostname, resolver, ipv6)], True)


class WanIpSensor(SensorEntity):
    """Implementation of a DNS IP sensor."""

    def __init__(self, name: str, hostname: str, resolver: str, ipv6: bool) -> None:
        """Initialize the DNS IP sensor."""
        self._attr_name = name
        self.hostname = hostname
        self.resolver = aiodns.DNSResolver()
        self.resolver.nameservers = [resolver]
        self.querytype = "AAAA" if ipv6 else "A"

    async def async_update(self) -> None:
        """Get the current DNS IP address for hostname."""
        try:
            response = await self.resolver.query(self.hostname, self.querytype)
        except DNSError as err:
            _LOGGER.warning("Exception while resolving host: %s", err)
            response = None

        if response:
            self._attr_state = response[0].host
        else:
            self._attr_state = None
