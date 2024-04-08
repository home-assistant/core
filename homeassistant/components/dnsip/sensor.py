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
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HOSTNAME,
    CONF_IPV4,
    CONF_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    CONF_ROUND_ROBIN,
    DEFAULT_ROUND_ROBIN,
    DOMAIN,
)

DEFAULT_RETRIES = 2

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


def join_ips(ips: list, querytype: str) -> str:
    """Join IPs into a single string."""

    if querytype == "AAAA":
        sorted_addresses = sorted(
            ips,
            key=lambda ip: [int(hextet, 16) for hextet in ip.split(":") if hextet],
        )
    else:
        sorted_addresses = sorted(
            ips,
            key=lambda ip: [int(octet) for octet in ip.split(".")],
        )
    filtered_addresses = []
    total_length = 0
    for address in sorted_addresses:
        if total_length + len(address) + 1 <= 255:
            filtered_addresses.append(address)
            total_length += len(address) + 1
        else:
            break
    return "\n".join(filtered_addresses)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the dnsip sensor entry."""

    hostname = entry.data[CONF_HOSTNAME]
    name = entry.data[CONF_NAME]

    resolver_ipv4 = entry.options[CONF_RESOLVER]
    resolver_ipv6 = entry.options[CONF_RESOLVER_IPV6]
    round_robin = entry.options.get(CONF_ROUND_ROBIN, DEFAULT_ROUND_ROBIN)

    entities = []
    if entry.data[CONF_IPV4]:
        entities.append(
            WanIpSensor(name, hostname, resolver_ipv4, False, round_robin=round_robin)
        )
    if entry.data[CONF_IPV6]:
        entities.append(
            WanIpSensor(name, hostname, resolver_ipv6, True, round_robin=round_robin)
        )

    async_add_entities(entities, update_before_add=True)


class WanIpSensor(SensorEntity):
    """Implementation of a DNS IP sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "dnsip"

    def __init__(
        self,
        name: str,
        hostname: str,
        resolver: str,
        ipv6: bool,
        round_robin: bool,
    ) -> None:
        """Initialize the DNS IP sensor."""
        self._attr_name = "IPv6" if ipv6 else None
        self._attr_unique_id = f"{hostname}_{ipv6}"
        self.hostname = hostname
        self.resolver = aiodns.DNSResolver()
        self.resolver.nameservers = [resolver]
        self.querytype = "AAAA" if ipv6 else "A"
        self._retries = DEFAULT_RETRIES
        self._round_robin = round_robin
        self._attr_extra_state_attributes = {
            "Resolver": resolver,
            "Querytype": self.querytype,
        }
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, hostname)},
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
            if self._round_robin:
                self._attr_native_value = join_ips(
                    [res.host for res in response], querytype=self.querytype
                )
            else:
                self._attr_native_value = response[0].host
            self._attr_available = True
            self._retries = DEFAULT_RETRIES
        elif self._retries > 0:
            self._retries -= 1
        else:
            self._attr_available = False
