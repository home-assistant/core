"""The Marstek integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from pymarstek import MarstekUDPClient, get_es_mode

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_UDP_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class MarstekRuntimeData:
    """Runtime data for Marstek config entries."""

    udp_client: MarstekUDPClient


type MarstekConfigEntry = ConfigEntry[MarstekRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Marstek component."""
    store = hass.data.setdefault(DOMAIN, {})
    if "udp_client" not in store:
        client = MarstekUDPClient()
        await client.async_setup()
        store["udp_client"] = client
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    _LOGGER.info("Setting up Marstek config entry: %s", entry.title)

    store = hass.data.setdefault(DOMAIN, {})
    if "udp_client" not in store:
        udp_client = MarstekUDPClient()
        await udp_client.async_setup()
        store["udp_client"] = udp_client
    else:
        udp_client = store["udp_client"]

    try:
        await udp_client.send_request(
            get_es_mode(0),
            entry.data["host"],
            DEFAULT_UDP_PORT,
            timeout=2.0,
        )
    except (TimeoutError, OSError, ValueError) as err:
        raise ConfigEntryNotReady("Unable to communicate with Marstek device") from err

    entry.runtime_data = MarstekRuntimeData(udp_client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Marstek config entry: %s", entry.title)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        client = hass.data.get(DOMAIN, {}).pop("udp_client", None)
        if client:
            await client.async_cleanup()

    return unload_ok
