"""Support for Roku."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PLAY_MEDIA_APP_ID, DEFAULT_PLAY_MEDIA_APP_ID
from .coordinator import RokuDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SELECT,
    Platform.SENSOR,
]

type RokuConfigEntry = ConfigEntry[RokuDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RokuConfigEntry) -> bool:
    """Set up Roku from a config entry."""
    if (device_id := entry.unique_id) is None:
        device_id = entry.entry_id

    coordinator = RokuDataUpdateCoordinator(
        hass,
        host=entry.data[CONF_HOST],
        device_id=device_id,
        play_media_app_id=entry.options.get(
            CONF_PLAY_MEDIA_APP_ID, DEFAULT_PLAY_MEDIA_APP_ID
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RokuConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: RokuConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)
