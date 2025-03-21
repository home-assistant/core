"""The Sky Remote Control integration."""

import logging

from skyboxremote import RemoteControl, SkyBoxConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS = [Platform.REMOTE]

_LOGGER = logging.getLogger(__name__)


type SkyRemoteConfigEntry = ConfigEntry[RemoteControl]


async def async_setup_entry(hass: HomeAssistant, entry: SkyRemoteConfigEntry) -> bool:
    """Set up Sky remote."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    _LOGGER.debug("Setting up Host: %s, Port: %s", host, port)
    remote = RemoteControl(host, port)
    try:
        await remote.check_connectable()
    except SkyBoxConnectionError as e:
        raise ConfigEntryNotReady from e

    entry.runtime_data = remote
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
