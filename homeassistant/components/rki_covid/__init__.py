"""RKI Covid numbers integration."""
import logging

from .coordinator import RkiCovidDataUpdateCoordinator


from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the RKI covid numbers integration from a config entry."""
    # create coordinator instance
    coordinator = RkiCovidDataUpdateCoordinator(hass)

    # trigger initial refresh
    await coordinator.async_config_entry_first_refresh()

    # put data into
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # setup platform
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
