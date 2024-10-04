"""The Sky Remote Control integration."""

import logging

from skyboxremote import RemoteControl, SkyBoxConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

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

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        manufacturer="SKY",
        model="Sky Box",
        name=host,
        identifiers={(DOMAIN, entry.entry_id)},
    )
    entry.runtime_data = remote
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
