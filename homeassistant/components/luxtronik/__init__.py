"""The Luxtronik integration."""
# region Imports
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_COORDINATOR, DOMAIN
from .coordinator import LuxtronikCoordinator

# endregion Imports

PLATFORMS: list[Platform] = [Platform.WATER_HEATER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Luxtronik from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Create API instance
    coordinator = LuxtronikCoordinator.connect(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(update_listener))

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = {}
    data[entry.entry_id][CONF_COORDINATOR] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Trigger a refresh again now that all platforms have registered
    hass.async_create_task(coordinator.async_refresh())

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
        await coordinator.async_shutdown()

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
