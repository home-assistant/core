"""The Marstek integration."""

import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Marstek integration.

    The shared UDP client is created once and lives for the lifetime of
    the integration. If creation fails, integration setup fails and the
    config entries stay not loaded; reloading the integration retries.
    """
    udp_client = await async_create_udp_client(hass)
    hass.data[MARSTEK_UDP_CLIENT] = udp_client

    async def close_udp_client(_: Event) -> None:
        """Clean up the shared UDP client when Home Assistant stops."""
        await udp_client.async_cleanup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_udp_client)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    coordinator = MarstekDataUpdateCoordinator(
        hass, entry, hass.data[MARSTEK_UDP_CLIENT]
    )
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
