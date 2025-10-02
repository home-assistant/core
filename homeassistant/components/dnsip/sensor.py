"""Get your own public IP address or that of any host."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
import logging
from typing import Literal

import aiodns
from aiodns.error import DNSError

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_HOSTNAME,
    CONF_IPV4,
    CONF_IPV6,
    CONF_PORT_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DOMAIN,
)

DEFAULT_RETRIES = 2
MAX_RESULTS = 10

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


def sort_ips(ips: list, querytype: Literal["A", "AAAA"]) -> list:
    """Join IPs into a single string."""

    if querytype == "AAAA":
        ips = [IPv6Address(ip) for ip in ips]
    else:
        ips = [IPv4Address(ip) for ip in ips]
    return [str(ip) for ip in sorted(ips)][:MAX_RESULTS]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the dnsip sensor entry."""

    hostname = entry.data[CONF_HOSTNAME]
    name = entry.data[CONF_NAME]

    nameserver_ipv4 = entry.options[CONF_RESOLVER]
    nameserver_ipv6 = entry.options[CONF_RESOLVER_IPV6]
    port_ipv4 = entry.options[CONF_PORT]
    port_ipv6 = entry.options[CONF_PORT_IPV6]

    entities = []
    if entry.data[CONF_IPV4]:
        entities.append(WanIpSensor(name, hostname, nameserver_ipv4, False, port_ipv4))
    if entry.data[CONF_IPV6]:
        entities.append(WanIpSensor(name, hostname, nameserver_ipv6, True, port_ipv6))

    async_add_entities(entities, update_before_add=True)


class WanIpSensor(SensorEntity):
    """Implementation of a DNS IP sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "dnsip"
    _unrecorded_attributes = frozenset({"resolver", "querytype", "ip_addresses"})

    resolver: aiodns.DNSResolver

    def __init__(
        self,
        name: str,
        hostname: str,
        nameserver: str,
        ipv6: bool,
        port: int,
    ) -> None:
        """Initialize the DNS IP sensor."""
        self._attr_name = "IPv6" if ipv6 else None
        self._attr_unique_id = f"{hostname}_{ipv6}"
        self.hostname = hostname
        self.port = port
        self.nameserver = nameserver
        self.querytype: Literal["A", "AAAA"] = "AAAA" if ipv6 else "A"
        self._retries = DEFAULT_RETRIES
        self._attr_extra_state_attributes = {
            "resolver": nameserver,
            "querytype": self.querytype,
        }
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, hostname)},
            manufacturer="DNS",
            model=aiodns.__version__,
            name=name,
        )
        self.create_dns_resolver()

    def create_dns_resolver(self) -> None:
        """Create the DNS resolver."""
        self.resolver = aiodns.DNSResolver(
            nameservers=[self.nameserver], tcp_port=self.port, udp_port=self.port
        )

    async def async_update(self) -> None:
        """Get the current DNS IP address for hostname."""
        if self.resolver._closed:  # noqa: SLF001
            self.create_dns_resolver()
        response = None
        try:
            async with asyncio.timeout(10):
                response = await self.resolver.query(self.hostname, self.querytype)
        except TimeoutError:
            await self.resolver.close()
        except DNSError as err:
            _LOGGER.warning("Exception while resolving host: %s", err)

        if response:
            sorted_ips = sort_ips(
                [res.host for res in response], querytype=self.querytype
            )
            self._attr_native_value = sorted_ips[0]
            self._attr_extra_state_attributes["ip_addresses"] = sorted_ips
            self._attr_available = True
            self._retries = DEFAULT_RETRIES
        elif self._retries > 0:
            self._retries -= 1
        else:
            self._attr_available = False
