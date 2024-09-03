"""The Sky Remote Control integration."""

from skyboxremote import RemoteControl, SkyBoxConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_LEGACY_CONTROL_PORT

PLATFORMS = [Platform.REMOTE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sky remote."""
    host = entry.data[CONF_HOST]
    port = 49160 if not entry.data[CONF_LEGACY_CONTROL_PORT] else 5900
    try:
        remote = RemoteControl(host, port)
        await remote.check_connectable()
    except SkyBoxConnectionError as e:
        raise ConfigEntryNotReady from e

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
