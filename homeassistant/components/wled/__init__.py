"""Support for WLED."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WLEDDataUpdateCoordinator

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WLED from a config entry."""
    coordinator = WLEDDataUpdateCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=coordinator.data.info.mac_address
        )

    # Set up all platforms for this device/entry.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload WLED config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

        # Ensure disconnected and cleanup stop sub
        await coordinator.wled.disconnect()
        if coordinator.unsub:
            coordinator.unsub()

        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)
