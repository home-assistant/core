"""The Bring! integration."""

from __future__ import annotations

import logging

from bring_api import Bring

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import (
    BringActivityCoordinator,
    BringConfigEntry,
    BringCoordinators,
    BringDataUpdateCoordinator,
)
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.SENSOR, Platform.TODO]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bring! services."""

    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BringConfigEntry) -> bool:
    """Set up Bring! from a config entry."""

    session = async_get_clientsession(hass)
    bring = Bring(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    coordinator = BringDataUpdateCoordinator(hass, entry, bring)
    await coordinator.async_config_entry_first_refresh()

    activity_coordinator = BringActivityCoordinator(hass, entry, coordinator)
    await activity_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = BringCoordinators(coordinator, activity_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BringConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
