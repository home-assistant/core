"""The DNS IP integration."""

import asyncio
from dataclasses import dataclass

import aiodns
from aiodns.error import DNSError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_HOSTNAME,
    CONF_IPV4,
    CONF_IPV6,
    CONF_PORT_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DEFAULT_PORT,
    PLATFORMS,
)


@dataclass
class DnsIPRuntimeData:
    """Runtime data for DNS IP integration."""

    resolver_ipv4: aiodns.DNSResolver
    resolver_ipv6: aiodns.DNSResolver


type DnsIPConfigEntry = ConfigEntry[DnsIPRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: DnsIPConfigEntry) -> bool:
    """Set up DNS IP from a config entry."""

    nameserver_ipv4 = entry.options[CONF_RESOLVER]
    nameserver_ipv6 = entry.options[CONF_RESOLVER_IPV6]
    port_ipv4 = entry.options[CONF_PORT]
    port_ipv6 = entry.options[CONF_PORT_IPV6]

    resolver_ipv4 = aiodns.DNSResolver(
        nameservers=[nameserver_ipv4], tcp_port=port_ipv4, udp_port=port_ipv4
    )
    resolver_ipv6 = aiodns.DNSResolver(
        nameservers=[nameserver_ipv6], tcp_port=port_ipv6, udp_port=port_ipv6
    )

    hostname = entry.data[CONF_HOSTNAME]
    try:
        async with asyncio.timeout(10):
            if entry.data[CONF_IPV4]:
                await resolver_ipv4.query(hostname, "A")
            elif entry.data[CONF_IPV6]:
                await resolver_ipv6.query(hostname, "AAAA")
    except (TimeoutError, DNSError) as err:
        await resolver_ipv4.close()
        await resolver_ipv6.close()
        raise ConfigEntryNotReady(f"DNS lookup failed for {hostname}: {err}") from err

    entry.runtime_data = DnsIPRuntimeData(
        resolver_ipv4=resolver_ipv4,
        resolver_ipv6=resolver_ipv6,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DnsIPConfigEntry) -> bool:
    """Unload DNS IP config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.resolver_ipv4.close()
        await entry.runtime_data.resolver_ipv6.close()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to a newer version."""

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version < 2 and config_entry.minor_version < 2:
        _LOGGER.debug(
            "Migrating configuration from version %s.%s",
            config_entry.version,
            config_entry.minor_version,
        )

        new_options = {**config_entry.options}
        new_options[CONF_PORT] = DEFAULT_PORT
        new_options[CONF_PORT_IPV6] = DEFAULT_PORT

        hass.config_entries.async_update_entry(
            config_entry, options=new_options, minor_version=2
        )

        _LOGGER.debug("Migration to configuration version %s.%s successful", 1, 2)

    if config_entry.version < 2 and config_entry.minor_version < 3:
        _LOGGER.debug(
            "Migrating configuration from version %s.%s",
            config_entry.version,
            config_entry.minor_version,
        )

        hass.config_entries.async_update_entry(
            config_entry, unique_id=None, minor_version=3
        )

        _LOGGER.debug("Migration to configuration version %s.%s successful", 1, 3)

    return True
