"""Integration for IRM KMI weather."""

import logging

from irm_kmi_api import IrmKmiApiClientHa

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, IRM_KMI_TO_HA_CONDITION_MAP, PLATFORMS, USER_AGENT
from .coordinator import (
    IrmKmiConfigEntry,
    IrmKmiCoordinator,
    IrmKmiPollenCoordinator,
    IrmKmiRuntimeData,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the IRM KMI integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IrmKmiConfigEntry) -> None:
    """Set up this integration using UI."""
    api_client = IrmKmiApiClientHa(
        session=async_get_clientsession(hass),
        user_agent=USER_AGENT,
        cdt_map=IRM_KMI_TO_HA_CONDITION_MAP,
    )

    weather_coordinator = IrmKmiCoordinator(hass, entry, api_client)
    await weather_coordinator.async_config_entry_first_refresh()

    # The pollen link comes from the forecast, so this refresh runs after it.
    # A pollen outage only makes the pollen sensors unavailable.
    pollen_coordinator = IrmKmiPollenCoordinator(hass, entry, api_client)
    await pollen_coordinator.async_refresh()

    entry.runtime_data = IrmKmiRuntimeData(
        weather=weather_coordinator, pollen=pollen_coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: IrmKmiConfigEntry) -> None:
    """Handle removal of an entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: IrmKmiConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
