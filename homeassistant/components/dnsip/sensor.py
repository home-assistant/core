"""Get your own public IP address or that of any host."""
from __future__ import annotations

from datetime import timedelta
import logging

import aiodns
from aiodns.error import DNSError

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HOSTNAME,
    CONF_IPV4,
    CONF_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the dnsip sensor entry."""

    hostname = entry.data[CONF_HOSTNAME]
    name = entry.data[CONF_NAME]

    resolver_ipv4 = entry.options[CONF_RESOLVER]
    resolver_ipv6 = entry.options[CONF_RESOLVER_IPV6]
    entities = []
    if entry.data[CONF_IPV4]:
        entities.append(WanIpSensor(name, hostname, resolver_ipv4, False))
    if entry.data[CONF_IPV6]:
        entities.append(WanIpSensor(name, hostname, resolver_ipv6, True))

    async_add_entities(entities, update_before_add=True)


class WanIpSensor(SensorEntity):
    """Implementation of a DNS IP sensor."""

    _attr_icon = "mdi:web"
    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        hostname: str,
        resolver: str,
        ipv6: bool,
    ) -> None:
        """Initialize the DNS IP sensor."""
        self._attr_name = "IPv6" if ipv6 else None
        self._attr_unique_id = f"{hostname}_{ipv6}"
        self.hostname = hostname
        self.resolver = aiodns.DNSResolver()
        self.resolver.nameservers = [resolver]
        self.querytype = "AAAA" if ipv6 else "A"
        self._attr_extra_state_attributes = {
            "Resolver": resolver,
            "Querytype": self.querytype,
        }
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{hostname}_{ipv6}")},
            manufacturer="DNS",
            model=aiodns.__version__,
            name=name,
        )

    async def async_update(self) -> None:
        """Get the current DNS IP address for hostname."""
        try:
            response = await self.resolver.query(self.hostname, self.querytype)
        except DNSError as err:
            _LOGGER.warning("Exception while resolving host: %s", err)
            response = None

        if response:
            self._attr_native_value = response[0].host
            self._attr_available = True
        else:
            self._attr_available = False
