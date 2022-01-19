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
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_HOSTNAME,
    CONF_IPV4,
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
        "Configuration of the DNS IP platform in YAML is deprecated and will be "
        "removed in Home Assistant 2022.4; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
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

    resolver_ipv4 = entry.options.get(CONF_RESOLVER, entry.data[CONF_RESOLVER])
    resolver_ipv6 = entry.options.get(
        CONF_RESOLVER_IPV6, entry.data[CONF_RESOLVER_IPV6]
    )
    entities = []
    if entry.data[CONF_IPV4]:
        entities.append(WanIpSensor(name, hostname, resolver_ipv4, False))
    if entry.data[CONF_IPV6]:
        entities.append(WanIpSensor(name, hostname, resolver_ipv6, True))

    async_add_entities(entities, update_before_add=True)


class WanIpSensor(SensorEntity):
    """Implementation of a DNS IP sensor."""

    _attr_icon = "mdi:web"

    def __init__(
        self,
        name: str,
        hostname: str,
        resolver: str,
        ipv6: bool,
    ) -> None:
        """Initialize the DNS IP sensor."""
        self._attr_name = f"{name} IPv6" if ipv6 else name
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
            name=hostname,
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
