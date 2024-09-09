"""The Sky Remote Control integration."""

import logging

from skyboxremote import RemoteControl, SkyBoxConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_PORT, LEGACY_PORT

PLATFORMS = [Platform.REMOTE]

_LOGGER = logging.getLogger(__name__)


async def async_find_box_port(host: str) -> int:
    """Find port box uses for communication."""
    logging.debug("Attempting to find port to connect to %s on", host)
    try:
        remote = RemoteControl(host, DEFAULT_PORT)
        await remote.check_connectable()
    except SkyBoxConnectionError:
        # Try legacy port if the default one failed
        remote = RemoteControl(host, LEGACY_PORT)
        await remote.check_connectable()
        return LEGACY_PORT
    return DEFAULT_PORT


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sky remote."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT)
    try:
        if port is None:
            port = await async_find_box_port(host)
            logging.info("Selected port %i to connect to %s", port, host)
            hass.config_entries.async_update_entry(
                entry, data=entry.data | {CONF_PORT: port}
            )
        remote = RemoteControl(host, port)
        await remote.check_connectable()
    except SkyBoxConnectionError as e:
        raise ConfigEntryNotReady from e

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
