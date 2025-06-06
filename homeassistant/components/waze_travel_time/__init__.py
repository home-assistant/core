"""The waze_travel_time component."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_EXCL_FILTER, CONF_INCL_FILTER, DEFAULT_FILTER, DOMAIN, SEMAPHORE
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    if SEMAPHORE not in hass.data.setdefault(DOMAIN, {}):
        hass.data.setdefault(DOMAIN, {})[SEMAPHORE] = asyncio.Semaphore(1)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""

    if config_entry.version == 1:
        _LOGGER.debug(
            "Migrating from version %s.%s",
            config_entry.version,
            config_entry.minor_version,
        )
        options = dict(config_entry.options)
        if (incl_filters := options.pop(CONF_INCL_FILTER, None)) not in {None, ""}:
            options[CONF_INCL_FILTER] = [incl_filters]
        else:
            options[CONF_INCL_FILTER] = DEFAULT_FILTER
        if (excl_filters := options.pop(CONF_EXCL_FILTER, None)) not in {None, ""}:
            options[CONF_EXCL_FILTER] = [excl_filters]
        else:
            options[CONF_EXCL_FILTER] = DEFAULT_FILTER
        hass.config_entries.async_update_entry(config_entry, options=options, version=2)
        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )
    return True
