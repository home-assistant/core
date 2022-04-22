"""Squeezebox Player integration."""
from __future__ import annotations

from aioslimproto import SlimServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

PLATFORMS = ["media_player"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    slimserver = SlimServer()
    try:
        await slimserver.start()
    except Exception as exc:  # pylint: disable=broad-except
        await slimserver.stop()
        raise ConfigEntryNotReady from exc

    hass.data[DOMAIN] = slimserver

    # initialize platform(s)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def handle_hass_event(event: Event):
        """Handle an incoming event from Home Assistant."""
        if event.event_type == EVENT_HOMEASSISTANT_STOP:
            await slimserver.stop()

    # setup event listeners
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_hass_event)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_success = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_success::
        await hass.data.pop(DOMAIN).stop()
    return unload_success
