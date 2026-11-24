"""The Marstek integration."""

import asyncio
import logging

from aiomarstek import MarstekUDPClient

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import (
    MARSTEK_UDP_CLIENT,
    MarstekConfigEntry,
    MarstekDataUpdateCoordinator,
)
from .helpers import async_create_udp_client

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

MARSTEK_UDP_CLIENT_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_udp_client_lock")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Marstek integration."""
    hass.data[MARSTEK_UDP_CLIENT_LOCK] = asyncio.Lock()
    return True


async def _async_get_udp_client(hass: HomeAssistant) -> MarstekUDPClient:
    """Return the shared UDP client, creating it on first use."""
    # Entries set up concurrently, so creation must happen only once.
    async with hass.data[MARSTEK_UDP_CLIENT_LOCK]:
        if (udp_client := hass.data.get(MARSTEK_UDP_CLIENT)) is not None:
            return udp_client

        try:
            udp_client = await async_create_udp_client(hass)
        except (TimeoutError, OSError, TypeError) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="udp_client_failed",
            ) from err
        hass.data[MARSTEK_UDP_CLIENT] = udp_client

    async def close_udp_client(_: Event) -> None:
        """Clean up the shared UDP client when Home Assistant stops."""
        await udp_client.async_cleanup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_udp_client)
    return udp_client


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> None:
    """Set up Marstek from a config entry."""
    coordinator = MarstekDataUpdateCoordinator(
        hass, entry, await _async_get_udp_client(hass)
    )
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
