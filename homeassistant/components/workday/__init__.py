"""Sensor to indicate whether the current day is a workday."""
import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import CONF_ADD_HOLIDAYS, CONF_REMOVE_HOLIDAYS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up workday from a config entry."""
    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options
    _async_import_options_from_data_if_missing(hass, entry)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


@callback
def _async_import_options_from_data_if_missing(hass: HomeAssistant, entry: ConfigEntry):
    options = dict(entry.options)
    data = dict(entry.data)
    if entry.source == SOURCE_IMPORT and not options:

        if CONF_ADD_HOLIDAYS in data:
            add_holidays = data.pop(CONF_ADD_HOLIDAYS)
            options[CONF_ADD_HOLIDAYS] = add_holidays

        if CONF_REMOVE_HOLIDAYS in data:
            remove_holidays = data.pop(CONF_REMOVE_HOLIDAYS)
            options[CONF_REMOVE_HOLIDAYS] = remove_holidays

        if options:
            hass.config_entries.async_update_entry(entry, data=data, options=options)
