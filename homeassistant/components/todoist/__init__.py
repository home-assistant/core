"""The todoist integration."""

import datetime
import logging

from todoist_api_python.api_async import TodoistAPIAsync

from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .coordinator import TodoistConfigEntry, TodoistCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=1)


PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: TodoistConfigEntry) -> bool:
    """Set up todoist from a config entry."""

    token = entry.data[CONF_TOKEN]
    api = TodoistAPIAsync(token)
    coordinator = TodoistCoordinator(hass, _LOGGER, entry, SCAN_INTERVAL, api, token)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TodoistConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
