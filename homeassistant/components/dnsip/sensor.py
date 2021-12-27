"""Get your own public IP address or that of any host."""
from __future__ import annotations

from datetime import timedelta
import logging

import aiodns
from aiodns.error import DNSError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_HOSTNAME,
    CONF_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DEFAULT_HOSTNAME,
    DEFAULT_IPV6,
    DEFAULT_RESOLVER,
    DEFAULT_RESOLVER_IPV6,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
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
    _LOGGER.warning(
        "Loading dnsip via platform setup is deprecated; Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the dnsip sensor entry."""

    hostname = entry.data[CONF_HOSTNAME]
    name = entry.data[CONF_NAME]
    ipv6 = entry.data[CONF_IPV6]

    resolver = entry.data[CONF_RESOLVER_IPV6] if ipv6 else entry.data[CONF_RESOLVER]

    async_add_entities(
        [WanIpSensor(name, hostname, resolver, ipv6, entry.entry_id)],
        update_before_add=True,
    )


class WanIpSensor(SensorEntity):
    """Implementation of a DNS IP sensor."""

    _attr_icon = "mdi:web"

    def __init__(
        self, name: str, hostname: str, resolver: str, ipv6: bool, entry_id: str
    ) -> None:
        """Initialize the DNS IP sensor."""
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{hostname}"
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
            self._attr_native_value = response[0].host
        else:
            self._attr_native_value = None
