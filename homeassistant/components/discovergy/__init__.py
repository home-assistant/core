"""The Discovergy integration."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging

import pydiscovergy
from pydiscovergy.authentication import BasicAuth
import pydiscovergy.error as discovergyError
from pydiscovergy.models import Meter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import APP_NAME, DOMAIN

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


@dataclass
class DiscovergyData:
    """Discovergy data class to share meters and api client."""

    api_client: pydiscovergy.Discovergy = field(default_factory=lambda: None)
    meters: list[Meter] = field(default_factory=lambda: [])
    coordinators: dict[str, DataUpdateCoordinator] = field(default_factory=lambda: {})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Discovergy from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # init discovergy data class
    discovergy_data = DiscovergyData(
        api_client=pydiscovergy.Discovergy(
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            app_name=APP_NAME,
            httpx_client=get_async_client(hass),
            authentication=BasicAuth(),
        ),
        meters=[],
        coordinators={},
    )

    try:
        # try to get meters from api to check if access token is still valid and later use
        # if no exception is raised everything is fine to go
        discovergy_data.meters = await discovergy_data.api_client.get_meters()
    except discovergyError.InvalidLogin as err:
        _LOGGER.debug("Invalid email or password: %s", err)
        raise ConfigEntryAuthFailed("Invalid email or password") from err
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.error("Unexpected error while communicating with API: %s", err)
        raise ConfigEntryNotReady(
            "Unexpected error while communicating with API"
        ) from err

    hass.data[DOMAIN][entry.entry_id] = discovergy_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)
