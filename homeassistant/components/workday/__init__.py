"""Sensor to indicate whether the current day is a workday."""
import asyncio
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_per_platform

from .const import CONF_ADD_HOLIDAYS, CONF_REMOVE_HOLIDAYS, DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the workday component."""
    hass.data.setdefault(DOMAIN, {})

    # Import configuration from sensor platform
    config_platform = config_per_platform(config, "binary_sensor")
    for p_type, p_config in config_platform:
        if p_type != DOMAIN:
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=p_config,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up workday from a config entry."""
    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options
    _async_import_options_from_data_if_missing(hass, entry)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

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
