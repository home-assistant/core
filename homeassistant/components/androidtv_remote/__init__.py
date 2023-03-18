"""The Android TV Remote integration."""
from __future__ import annotations

from androidtvremote2 import (
    AndroidTVRemote,
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .helpers import create_api

PLATFORMS: list[Platform] = [Platform.REMOTE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Android TV Remote from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    api = create_api(hass, entry.data[CONF_HOST])
    try:
        await api.async_connect()
    except InvalidAuth as exc:
        raise ConfigEntryAuthFailed from exc
    except (CannotConnect, ConnectionClosed) as exc:
        raise ConfigEntryNotReady from exc

    def reauth_needed():
        entry.async_start_reauth(hass)

    api.keep_reconnecting(reauth_needed)

    hass.data[DOMAIN][entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def on_hass_stop(event):
        """Stop push updates when hass stops."""
        api.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        api: AndroidTVRemote = hass.data[DOMAIN].pop(entry.entry_id)
        api.disconnect()

    return unload_ok
