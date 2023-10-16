"""The trafikverket_camera component."""
from __future__ import annotations

import logging

from pytrafikverket.exceptions import (
    InvalidAuthentication,
    MultipleCamerasFound,
    NoCameraFound,
    UnknownError,
)
from pytrafikverket.trafikverket_camera import TrafikverketCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCATION, DOMAIN, PLATFORMS
from .coordinator import TVDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Trafikverket Camera from a config entry."""

    if entry.unique_id and entry.unique_id.startswith(DOMAIN):
        await async_new_unique_id(hass, entry)

    coordinator = TVDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Trafikverket Camera config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_new_unique_id(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Change unique id to camera_id."""
    # Change entry unique id from location to camera id
    camera_info = None
    location = entry.data[CONF_LOCATION]
    api_key = entry.data[CONF_API_KEY]

    web_session = async_get_clientsession(hass)
    camera_api = TrafikverketCamera(web_session, api_key)

    try:
        camera_info = await camera_api.async_get_camera(location)
    except UnknownError as err:
        _LOGGER.warning(
            "Could not change the config entry. No connection to the api: %s", err
        )
    except InvalidAuthentication as err:
        raise ConfigEntryAuthFailed from err
    except (MultipleCamerasFound, NoCameraFound):
        _LOGGER.warning(
            "Could not change the config entry. Location gives incorrect data"
        )

    if camera_info and (camera_id := camera_info.camera_id):
        _LOGGER.debug(
            "Changed Trafikverket Camera config entry unique id to %s",
            camera_id,
        )
        hass.config_entries.async_update_entry(
            entry,
            unique_id=camera_id,
        )
