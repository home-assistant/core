"""The Android TV Remote integration."""

from __future__ import annotations

from asyncio import timeout
import logging

from androidtvremote2 import (
    AndroidTVRemote,
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .helpers import create_api, get_enable_ime

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.REMOTE]

AndroidTVRemoteConfigEntry = ConfigEntry[AndroidTVRemote]


async def async_setup_entry(
    hass: HomeAssistant, entry: AndroidTVRemoteConfigEntry
) -> bool:
    """Set up Android TV Remote from a config entry."""
    _LOGGER.debug("async_setup_entry: %s", entry.data)
    api = create_api(hass, entry.data[CONF_HOST], get_enable_ime(entry))

    @callback
    def is_available_updated(is_available: bool) -> None:
        if is_available:
            _LOGGER.info(
                "Reconnected to %s at %s", entry.data[CONF_NAME], entry.data[CONF_HOST]
            )
        else:
            _LOGGER.warning(
                "Disconnected from %s at %s",
                entry.data[CONF_NAME],
                entry.data[CONF_HOST],
            )

    api.add_is_available_updated_callback(is_available_updated)

    try:
        async with timeout(5.0):
            await api.async_connect()
    except InvalidAuth as exc:
        # The Android TV is hard reset or the certificate and key files were deleted.
        raise ConfigEntryAuthFailed from exc
    except (CannotConnect, ConnectionClosed, TimeoutError) as exc:
        # The Android TV is network unreachable. Raise exception and let Home Assistant retry
        # later. If device gets a new IP address the zeroconf flow will update the config.
        raise ConfigEntryNotReady from exc

    def reauth_needed() -> None:
        """Start a reauth flow if Android TV is hard reset while reconnecting."""
        entry.async_start_reauth(hass)

    # Start a task (canceled in disconnect) to keep reconnecting if device becomes
    # network unreachable. If device gets a new IP address the zeroconf flow will
    # update the config entry data and reload the config entry.
    api.keep_reconnecting(reauth_needed)

    entry.runtime_data = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def on_hass_stop(event: Event) -> None:
        """Stop push updates when hass stops."""
        api.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    entry.async_on_unload(api.disconnect)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry: %s", entry.data)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug(
        "async_update_options: data: %s options: %s", entry.data, entry.options
    )
    await hass.config_entries.async_reload(entry.entry_id)
