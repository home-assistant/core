"""The IMGW-PIB integration."""

from __future__ import annotations

import logging

from aiohttp import ClientError
from imgw_pib import ImgwPib
from imgw_pib.exceptions import ApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_STATION_ID, DOMAIN
from .coordinator import ImgwPibDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IMGW-PIB from a config entry."""
    station_id: str = entry.data[CONF_STATION_ID]

    _LOGGER.debug("Using hydrological station ID: %s", station_id)

    client_session = async_get_clientsession(hass)

    try:
        imgwpib = await ImgwPib.create(
            client_session, hydrological_station_id=station_id
        )
    except (ClientError, TimeoutError, ApiError) as err:
        raise ConfigEntryNotReady from err

    coordinator = ImgwPibDataUpdateCoordinator(hass, imgwpib, station_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
