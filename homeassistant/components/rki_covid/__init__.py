"""RKI Covid numbers integration."""
import asyncio
from datetime import timedelta
import logging

from homeassistant.helpers.typing import ConfigType
from homeassistant.components.rki_covid.coordinator import RkiCovidDataUpdateCoordinator


from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_SCAN_INTERVAL, Platform

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup the RKI covid numbers integration from a config entry."""
    _LOGGER.debug("async_setup_entry from a config entry")

    # create coordinator instance
    coordinator = RkiCovidDataUpdateCoordinator(hass)

    # trigger initial refresh
    await coordinator.async_config_entry_first_refresh()

    # put data into
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
    }

    # set default options if not already set
    if not entry.options:
        options = {
            CONF_SCAN_INTERVAL: entry.data.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        }
        hass.config_entries.async_update_entry(entry, options=options)

    # setup platform
    hass.config_entries.async_setup_platforms(entry, [Platform.SENSOR])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry %s", entry.data)
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
