"""The Wallbox integration."""
import asyncio
import logging

from wallbox import Wallbox

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_CONNECTIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "lock", "number", "switch"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Wallbox component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Wallbox from a config entry."""

    wallbox = Wallbox(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    try:
        await hass.async_add_executor_job(wallbox.authenticate)

    except ConnectionError as exception:
        _LOGGER.error("Unable to fetch data from Wallbox Switch. %s", exception)

        return False

    hass.data.setdefault(DOMAIN, {CONF_CONNECTIONS: {}})
    hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id] = wallbox

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
