"""Support for WLED."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import LOGGER
from .coordinator import WLEDDataUpdateCoordinator

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
)

type WLEDConfigEntry = ConfigEntry[WLEDDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WLEDConfigEntry) -> bool:
    """Set up WLED from a config entry."""
    coordinator = WLEDDataUpdateCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    if coordinator.data.info.leds.cct:
        LOGGER.error(
            (
                "WLED device '%s' has a CCT channel, which is not supported by "
                "this integration"
            ),
            entry.title,
        )
        return False

    entry.runtime_data = coordinator

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WLEDConfigEntry) -> bool:
    """Unload WLED config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data

        # Ensure disconnected and cleanup stop sub
        await coordinator.wled.disconnect()
        if coordinator.unsub:
            coordinator.unsub()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)
