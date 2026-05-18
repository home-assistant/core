"""Get your own public IP address or that of any host."""

import asyncio
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
import logging
from typing import TYPE_CHECKING, Literal

import aiodns
from aiodns.error import DNSError

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DnsIPConfigEntry
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
    entry: DnsIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the dnsip sensor entry."""

    hostname = entry.data[CONF_HOSTNAME]
    name = entry.data[CONF_NAME]

    entities = []
    if entry.data[CONF_IPV4]:
        entities.append(
            WanIpSensor(
                entry,
                name,
                hostname,
                entry.options[CONF_RESOLVER],
                False,
                entry.options[CONF_PORT],
            )
        )
    if entry.data[CONF_IPV6]:
        entities.append(
            WanIpSensor(
                entry,
                name,
                hostname,
                entry.options[CONF_RESOLVER_IPV6],
                True,
                entry.options[CONF_PORT_IPV6],
            )
        )

    async_add_entities(entities, update_before_add=True)


class WanIpSensor(SensorEntity):
    """Implementation of a DNS IP sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "dnsip"
    _unrecorded_attributes = frozenset({"resolver", "querytype", "ip_addresses"})

    def __init__(
        self,
        entry: DnsIPConfigEntry,
        name: str,
        hostname: str,
        nameserver: str,
        ipv6: bool,
        port: int,
    ) -> None:
        """Initialize the DNS IP sensor."""
        self.entry = entry
        self.ipv6 = ipv6
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

    @property
    def _resolver(self) -> aiodns.DNSResolver:
        """Return the active DNS resolver from runtime data."""
        resolver = (
            self.entry.runtime_data.resolver_ipv6
            if self.ipv6
            else self.entry.runtime_data.resolver_ipv4
        )
        if TYPE_CHECKING:
            assert resolver is not None
        return resolver

    def create_dns_resolver(self) -> None:
        """Create a new DNS resolver and store it on runtime data."""
        new_resolver = aiodns.DNSResolver(
            nameservers=[self.nameserver], tcp_port=self.port, udp_port=self.port
        )
        if self.ipv6:
            self.entry.runtime_data.resolver_ipv6 = new_resolver
        else:
            self.entry.runtime_data.resolver_ipv4 = new_resolver

    async def async_update(self) -> None:
        """Get the current DNS IP address for hostname."""
        if self._resolver._closed:  # noqa: SLF001
            self.create_dns_resolver()
        response = None
        try:
            async with asyncio.timeout(10):
                response = await self._resolver.query(self.hostname, self.querytype)
        except TimeoutError as err:
            _LOGGER.debug("Timeout while resolving host: %s", err)
            await self._resolver.close()
        except DNSError as err:
            _LOGGER.warning("Exception while resolving host: %s", err)
            await self._resolver.close()

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
