"""The youless integration."""
from datetime import timedelta
import logging
from urllib.error import URLError

from youless_api import YoulessAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up youless from a config entry."""
    api = YoulessAPI(entry.data[CONF_HOST])

    try:
        await hass.async_add_executor_job(api.initialize)
    except URLError as exception:
        raise ConfigEntryNotReady from exception

    async def async_update_data():
        """Fetch data from the API."""
        await hass.async_add_executor_job(api.update)
        return api

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="youless_gateway",
        update_method=async_update_data,
        update_interval=timedelta(seconds=2),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
