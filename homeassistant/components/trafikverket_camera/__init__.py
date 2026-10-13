"""The trafikverket_camera component."""

import logging

from pytrafikverket import TrafikverketCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS
from .coordinator import TVDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

TVCameraConfigEntry = ConfigEntry[TVDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TVCameraConfigEntry) -> bool:
    """Set up Trafikverket Camera from a config entry."""

    coordinator = TVDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TVCameraConfigEntry) -> bool:
    """Unload Trafikverket Camera config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: TVCameraConfigEntry) -> bool:
    """Migrate old entry."""
    api_key = entry.data[CONF_API_KEY]
    web_session = async_get_clientsession(hass)
    camera_api = TrafikverketCamera(web_session, api_key)
    # Change entry unique id from location to camera id
    if entry.version == 1:
        location = entry.data[CONF_LOCATION]

        try:
            camera_info = await camera_api.async_get_camera(location)
        except Exception as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="migration_cannot_connect",
                translation_placeholders={"location": location},
            ) from err

        if camera_id := camera_info.camera_id:
            hass.config_entries.async_update_entry(
                entry,
                unique_id=f"{DOMAIN}-{camera_id}",
                version=2,
            )
            _LOGGER.debug(
                "Migrated Trafikverket Camera config entry unique id to %s",
                camera_id,
            )
        else:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="migration_no_camera_id",
                translation_placeholders={"location": location},
            )

    # Change entry data from location to id
    if entry.version == 2:
        location = entry.data[CONF_LOCATION]

        try:
            camera_info = await camera_api.async_get_camera(location)
        except Exception as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="migration_cannot_connect",
                translation_placeholders={"location": location},
            ) from err

        if camera_id := camera_info.camera_id:
            _LOGGER.debug(
                "Migrate Trafikverket Camera config entry unique id to %s",
                camera_id,
            )
            new_data = entry.data.copy()
            new_data.pop(CONF_LOCATION)
            new_data[CONF_ID] = camera_id
            hass.config_entries.async_update_entry(entry, data=new_data, version=3)
            return True
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="migration_no_camera_id",
            translation_placeholders={"location": location},
        )
    return True
