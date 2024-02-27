"""The air-Q integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CLIP_NEGATIVE, CONF_RETURN_AVERAGE, DOMAIN
from .coordinator import AirQCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up air-Q from a config entry."""

    coordinator = AirQCoordinator(
        hass,
        entry,
        clip_negative=entry.options.get(CONF_CLIP_NEGATIVE, True),
        return_average=entry.options.get(CONF_RETURN_AVERAGE, True),
    )

    # Query the device for the first time and initialise coordinator.data
    await coordinator.async_config_entry_first_refresh()

    # Record the coordinator in a global store
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
