"""The todoist integration."""

import datetime as dt
import logging

from todoist_api_python.api_async import TodoistAPIAsync

from homeassistant.const import CONF_TOKEN, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import TodoistConfigEntry, TodoistCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = dt.timedelta(minutes=1)


PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.TODO]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TodoistConfigEntry) -> None:
    """Set up todoist from a config entry."""

    token = entry.data[CONF_TOKEN]
    # The SDK creates an httpx client on init, which loads SSL certs from disk.
    api = await hass.async_add_executor_job(TodoistAPIAsync, token)
    coordinator = TodoistCoordinator(hass, _LOGGER, entry, SCAN_INTERVAL, api, token)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await api.close()
        raise

    # Home Assistant shutdown does not unload config entries, so close the
    # SDK's HTTP client explicitly when Home Assistant stops.
    async def _close_api(_: Event) -> None:
        await api.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close_api)
    )


async def async_unload_entry(hass: HomeAssistant, entry: TodoistConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.api.close()
