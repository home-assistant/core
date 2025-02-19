"""The Remote Calendar integration."""

import logging

from httpx import ConnectError, HTTPStatusError, UnsupportedProtocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import RemoteCalendarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CALENDAR]

type RemoteCalendarConfigEntry = ConfigEntry[RemoteCalendarDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: RemoteCalendarConfigEntry
) -> bool:
    """Set up Remote Calendar from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = RemoteCalendarDataUpdateCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except (UnsupportedProtocol, ConnectError, HTTPStatusError, ValueError) as err:
        raise ConfigEntryNotReady(f"Failed to fetch calendar data: {err}") from err
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RemoteCalendarConfigEntry
) -> bool:
    """Handle unload of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
