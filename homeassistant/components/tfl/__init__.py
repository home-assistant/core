"""The Transport for London integration."""
from __future__ import annotations

import logging
from urllib.error import HTTPError, URLError

from tflwrapper import stopPoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .config_helper import config_from_entry
from .const import CONF_API_APP_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Transport for London from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    conf = config_from_entry(entry)

    stop_point_api = stopPoint(conf[CONF_API_APP_KEY])
    try:
        categories = await hass.async_add_executor_job(
            stop_point_api.getCategories
        )  # Check can call endpoint.
    except HTTPError as exception:
        # TfL's API returns a 429 if you pass an invalid app_key, but we also check
        # for other reasonable error codes in case their behaviour changes
        error_code = exception.code
        if error_code in (429, 401, 403):
            raise ConfigEntryAuthFailed(
                "Authentication failure for app_key=" + conf[CONF_API_APP_KEY]
            ) from exception

        raise ConfigEntryNotReady(
            "Connection error whilst connecting to TfL"
        ) from exception
    except URLError as exception:
        raise ConfigEntryNotReady(
            "Connection error whilst connecting to TfL"
        ) from exception

    _LOGGER.debug(
        "Setting up %s integration, got stoppoint categories %s", DOMAIN, categories
    )

    hass.data[DOMAIN][entry.entry_id] = stop_point_api
    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("update_listener called")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
