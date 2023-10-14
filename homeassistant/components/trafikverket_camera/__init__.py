"""The trafikverket_camera component."""
from __future__ import annotations

import logging

from pytrafikverket.trafikverket_camera import TrafikverketCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCATION, DOMAIN, PLATFORMS
from .coordinator import TVDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Trafikverket Camera from a config entry."""

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # Change entry unique id from location to camera id
    if entry.version == 1:
        location = entry.data[CONF_LOCATION]
        api_key = entry.data[CONF_API_KEY]

        web_session = async_get_clientsession(hass)
        camera_api = TrafikverketCamera(web_session, api_key)

        try:
            camera_info = await camera_api.async_get_camera(location)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(
                "Could not migrate the config entry. No connection to the api"
            )
            return False

        if camera_id := camera_info.camera_id:
            entry.version = 2
            _LOGGER.debug(
                "Migrate Trafikverket Camera config entry unique id to %s",
                camera_id,
            )
            hass.config_entries.async_update_entry(
                entry,
                unique_id=f"{DOMAIN}-{camera_id}",
            )
            return True
        _LOGGER.error("Could not migrate the config entry. Camera has no id")
        return False
    return True
