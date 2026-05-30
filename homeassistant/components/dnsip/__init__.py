"""The DNS IP integration."""

import asyncio
from dataclasses import dataclass
import logging

import aiodns
from aiodns.error import DNSError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
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

_LOGGER = logging.getLogger(__name__)


@dataclass
class DnsIPRuntimeData:
    """Runtime data for DNS IP integration."""

    resolver_ipv4: aiodns.DNSResolver | None
    resolver_ipv6: aiodns.DNSResolver | None


type DnsIPConfigEntry = ConfigEntry[DnsIPRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: DnsIPConfigEntry) -> bool:
    """Set up DNS IP from a config entry."""

    hostname = entry.data[CONF_HOSTNAME]
    resolver_ipv4: aiodns.DNSResolver | None = None
    resolver_ipv6: aiodns.DNSResolver | None = None
    queries: list = []

    if entry.data[CONF_IPV4]:
        resolver_ipv4 = aiodns.DNSResolver(
            nameservers=[entry.options[CONF_RESOLVER]],
            tcp_port=entry.options[CONF_PORT],
            udp_port=entry.options[CONF_PORT],
        )
        queries.append(resolver_ipv4.query(hostname, "A"))

    if entry.data[CONF_IPV6]:
        resolver_ipv6 = aiodns.DNSResolver(
            nameservers=[entry.options[CONF_RESOLVER_IPV6]],
            tcp_port=entry.options[CONF_PORT_IPV6],
            udp_port=entry.options[CONF_PORT_IPV6],
        )
        queries.append(resolver_ipv6.query(hostname, "AAAA"))

    async def _close_resolvers() -> None:
        if resolver_ipv4 is not None:
            await resolver_ipv4.close()
        if resolver_ipv6 is not None:
            await resolver_ipv6.close()

    try:
        async with asyncio.timeout(10):
            results = await asyncio.gather(*queries, return_exceptions=True)
    except TimeoutError as err:
        await _close_resolvers()
        raise ConfigEntryNotReady(
            f"DNS lookup timed out for {hostname}: {err}"
        ) from err

    errors = [
        result for result in results if isinstance(result, (TimeoutError, DNSError))
    ]
    if errors and len(errors) == len(results):
        await _close_resolvers()
        raise ConfigEntryNotReady(
            f"DNS lookup failed for {hostname}: {errors[0]}"
        ) from errors[0]

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
        if entry.runtime_data.resolver_ipv4 is not None:
            await entry.runtime_data.resolver_ipv4.close()
        if entry.runtime_data.resolver_ipv6 is not None:
            await entry.runtime_data.resolver_ipv6.close()
    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: DnsIPConfigEntry
) -> bool:
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
