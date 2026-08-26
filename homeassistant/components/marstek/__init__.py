"""The Marstek integration."""
# pylint: disable=home-assistant-use-runtime-data  # Shared UDP client spans entries

import logging

from aiomarstek import MarstekUDPClient

from homeassistant.components import network
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .const import DOMAIN
from .coordinator import MarstekConfigEntry, MarstekDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


class MarstekData:
    """Shared runtime data for all Marstek config entries."""

    __slots__ = ("entry_count", "udp_client")

    def __init__(self, udp_client: MarstekUDPClient) -> None:
        """Initialize shared runtime data."""
        self.udp_client = udp_client
        self.entry_count = 0


async def async_create_udp_client(hass: HomeAssistant) -> MarstekUDPClient:
    """Create a configured UDP client for this Home Assistant instance."""
    client = MarstekUDPClient()
    try:
        await client.async_setup()
        addresses = await network.async_get_ipv4_broadcast_addresses(hass)
    except (TimeoutError, OSError, TypeError):
        await client.async_cleanup()
        raise

    client.set_broadcast_addresses([str(address) for address in addresses])
    return client


async def _async_release_udp_client(hass: HomeAssistant, data: MarstekData) -> None:
    """Release a reference to the shared UDP client."""
    data.entry_count -= 1
    if data.entry_count == 0:
        await data.udp_client.async_cleanup()
        hass.data.pop(DOMAIN, None)


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    data = hass.data.get(DOMAIN)
    if data is None:
        try:
            udp_client = await async_create_udp_client(hass)
        except (TimeoutError, OSError, TypeError) as err:
            raise ConfigEntryNotReady(
                "Unable to set up the Marstek UDP client"
            ) from err
        data = MarstekData(udp_client)
        hass.data[DOMAIN] = data
    data.entry_count += 1

    coordinator = MarstekDataUpdateCoordinator(hass, entry, data.udp_client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except (ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady):
        await _async_release_udp_client(hass, data)
        raise

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await _async_release_udp_client(hass, hass.data[DOMAIN])

    return unload_ok
