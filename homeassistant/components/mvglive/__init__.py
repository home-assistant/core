"""The mvglive component."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENABLE_MESSAGES,
    CONF_NUMBER,
    CONF_PRODUCTS,
    CONF_STATION_ID,
    CONF_TIMEOFFSET,
    DEFAULT_ENABLE_MESSAGES,
    DEFAULT_NUMBER,
    DEFAULT_TIMEOFFSET,
)
from .coordinator import MvgConfigEntry, MvgDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MvgConfigEntry) -> bool:
    """Set up MVG from a config entry."""
    coordinator = MvgDataUpdateCoordinator(
        hass,
        entry,
        entry.data[CONF_STATION_ID],
        entry.options.get(CONF_TIMEOFFSET, DEFAULT_TIMEOFFSET),
        entry.options.get(CONF_NUMBER, DEFAULT_NUMBER),
        entry.options.get(CONF_PRODUCTS),
        entry.options.get(CONF_ENABLE_MESSAGES, DEFAULT_ENABLE_MESSAGES),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: MvgConfigEntry) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MvgConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
