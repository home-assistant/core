"""The Govee Light local integration."""

import asyncio
from contextlib import suppress
from errno import EADDRINUSE, EADDRNOTAVAIL, EMFILE, ENETDOWN, ENETUNREACH, ENOBUFS
import logging

from govee_local_api.controller import LISTENING_PORT

from homeassistant.components import network
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DISCOVERY_TIMEOUT, DOMAIN
from .coordinator import GoveeLocalApiCoordinator, GoveeLocalConfigEntry

PLATFORMS: list[Platform] = [Platform.LIGHT]

# Bind errors that clear up on their own (port freed, adapter back, resources
# released); anything else needs user intervention and must not retry.
TRANSIENT_BIND_ERRNOS = frozenset(
    {EADDRINUSE, EADDRNOTAVAIL, EMFILE, ENETDOWN, ENETUNREACH, ENOBUFS}
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: GoveeLocalConfigEntry) -> bool:
    """Set up Govee light local from a config entry."""

    listening_addresses = await async_get_listening_addresses(hass)
    _LOGGER.debug("Enabled listening addresses: %s", listening_addresses)

    if not listening_addresses:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="no_listening_addresses"
        )

    coordinator: GoveeLocalApiCoordinator = GoveeLocalApiCoordinator(
        hass=hass, config_entry=entry, listening_addresses=listening_addresses
    )

    async def await_cleanup() -> None:
        cleanup_complete_event = coordinator.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup_complete_event.wait(), 1)

    entry.async_on_unload(await_cleanup)

    try:
        await coordinator.start()
    except OSError as ex:
        # No address bound. Adapters are enumerated once at startup, so retry
        # rather than fail: a late or stale adapter recovers on the next attempt.
        if ex.errno == EADDRINUSE:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="port_in_use",
                translation_placeholders={"port": LISTENING_PORT},
            ) from ex
        if ex.errno in TRANSIENT_BIND_ERRNOS:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="bind_failed",
                translation_placeholders={"error": ex.strerror or str(ex)},
            ) from ex
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="bind_failed",
            translation_placeholders={"error": ex.strerror or str(ex)},
        ) from ex

    await coordinator.async_config_entry_first_refresh()

    try:
        async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
            while not coordinator.devices:
                await asyncio.sleep(delay=1)
    except TimeoutError as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="no_devices_found"
        ) from ex

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoveeLocalConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_get_listening_addresses(hass: HomeAssistant) -> list[str]:
    """Get the enabled IPv4 source addresses, with network mask, for Govee local."""
    adapters = await network.async_get_adapters(hass)
    for adapter in adapters:
        _LOGGER.debug(
            "Adapter %s (%s): %s",
            adapter["name"],
            "enabled" if adapter["enabled"] else "disabled",
            [f"{ipv4['address']}/{ipv4['network_prefix']}" for ipv4 in adapter["ipv4"]],
        )
    return sorted(
        {
            f"{ipv4['address']}/{ipv4['network_prefix']}"
            for adapter in adapters
            if adapter["enabled"]
            for ipv4 in adapter["ipv4"]
        }
    )
