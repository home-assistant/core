"""The waze_travel_time component."""

import asyncio
import logging

from pywaze.route_calculator import WazeRouteCalculator

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_REGION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BASE_COORDINATES,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_TIME_DELTA,
    DEFAULT_FILTER,
    DEFAULT_TIME_DELTA,
    DOMAIN,
    SEMAPHORE_KEY,
)
from .coordinator import WazeTravelTimeCoordinator
from .helpers import default_base_coordinates_for_region
from .services import async_setup_services

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Waze."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    if SEMAPHORE_KEY not in hass.data:
        hass.data[SEMAPHORE_KEY] = asyncio.Semaphore(1)

    httpx_client = get_async_client(hass)
    client = WazeRouteCalculator(
        region=config_entry.data[CONF_REGION].upper(), client=httpx_client
    )

    coordinator = WazeTravelTimeCoordinator(hass, config_entry, client)
    config_entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()

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

    if config_entry.version == 2 and config_entry.minor_version == 1:
        _LOGGER.debug(
            "Migrating from version %s.%s",
            config_entry.version,
            config_entry.minor_version,
        )
        options = dict(config_entry.options)
        options[CONF_TIME_DELTA] = DEFAULT_TIME_DELTA
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=2
        )
        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

    if config_entry.version == 2 and config_entry.minor_version == 2:
        _LOGGER.debug(
            "Migrating from version %s.%s",
            config_entry.version,
            config_entry.minor_version,
        )
        options = dict(config_entry.options)
        options.setdefault(
            CONF_BASE_COORDINATES,
            default_base_coordinates_for_region(config_entry.data[CONF_REGION]),
        )
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=3
        )
        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

    return True
