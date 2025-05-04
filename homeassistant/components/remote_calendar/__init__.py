"""The Remote Calendar integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import RemoteCalendarConfigEntry, RemoteCalendarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup_entry(
    hass: HomeAssistant, entry: RemoteCalendarConfigEntry
) -> bool:
    """Set up Remote Calendar from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = RemoteCalendarDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RemoteCalendarConfigEntry
) -> bool:
    """Handle unload of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload remote calendar component when options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)
