"""The Marstek integration."""

from __future__ import annotations

import logging

from pymarstek import MarstekUDPClient, get_es_mode

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_UDP_PORT, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MarstekConfigEntry = ConfigEntry[MarstekUDPClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Marstek component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    _LOGGER.info("Setting up Marstek config entry: %s", entry.title)

    udp_client = MarstekUDPClient()
    await udp_client.async_setup()

    try:
        await udp_client.send_request(
            get_es_mode(0),
            entry.data["host"],
            DEFAULT_UDP_PORT,
            timeout=2.0,
        )
    except (TimeoutError, OSError, ValueError) as err:
        await udp_client.async_cleanup()
        raise ConfigEntryNotReady("Unable to communicate with Marstek device") from err

    entry.runtime_data = udp_client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Marstek config entry: %s", entry.title)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.runtime_data:
        await entry.runtime_data.async_cleanup()

    return unload_ok
