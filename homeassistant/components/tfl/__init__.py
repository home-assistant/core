"""The Transport for London integration."""

from __future__ import annotations

import logging
from urllib.error import HTTPError

from tflwrapper import stopPoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .common import CannotConnect, InvalidAuth, call_tfl_api
from .const import CONF_API_APP_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type TfLConfigEntry = ConfigEntry[stopPoint]


async def async_setup_entry(hass: HomeAssistant, entry: TfLConfigEntry) -> bool:
    """Set up Transport for London from a config entry."""

    app_key = entry.data[CONF_API_APP_KEY]
    stop_point_api = stopPoint(app_key)
    try:
        # Check can call an endpoint.
        categories = await call_tfl_api(hass, stop_point_api.getCategories)
    except InvalidAuth as exception:
        raise ConfigEntryAuthFailed(
            "Authentication failure for app_key=" + app_key
        ) from exception
    except (HTTPError, CannotConnect) as exception:
        raise ConfigEntryNotReady(
            "Connection error whilst connecting to TfL"
        ) from exception

    _LOGGER.debug(
        "Setting up %s integration, got stoppoint categories %s", DOMAIN, categories
    )

    entry.runtime_data = stop_point_api
    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: TfLConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("update_listener called")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TfLConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
