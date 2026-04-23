"""SlimProto Player integration."""

from __future__ import annotations

from aioslimproto.server import SlimServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr

PLATFORMS = [Platform.MEDIA_PLAYER]

type SlimProtoConfigEntry = ConfigEntry[SlimServer]


async def async_setup_entry(hass: HomeAssistant, entry: SlimProtoConfigEntry) -> bool:
    """Set up from a config entry."""
    slimserver = SlimServer()
    await slimserver.start()

    entry.runtime_data = slimserver

    # initialize platform(s)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # setup event listeners
    async def on_hass_stop(event: Event) -> None:
        """Handle incoming stop event from Home Assistant."""
        await slimserver.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: SlimProtoConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SlimProtoConfigEntry) -> bool:
    """Unload a config entry."""
    unload_success = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_success:
        await entry.runtime_data.stop()
    return unload_success
