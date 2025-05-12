"""The Volvo integration."""

from __future__ import annotations

import logging

from aiohttp import ClientResponseError
from volvocarsapi.api import VolvoCarsApi

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import VolvoAuth
from .const import CONF_VIN, PLATFORMS
from .coordinator import VolvoConfigEntry, VolvoData, VolvoDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: VolvoConfigEntry) -> bool:
    """Set up Volvo from a config entry."""

    # Create APIs
    implementation = await async_get_config_entry_implementation(hass, entry)
    oauth_session = OAuth2Session(hass, entry, implementation)
    web_session = async_get_clientsession(hass)
    auth = VolvoAuth(web_session, oauth_session)

    try:
        await auth.async_get_access_token()
    except ClientResponseError as err:
        if err.status == 401:
            raise ConfigEntryAuthFailed from err

        raise ConfigEntryNotReady from err

    api = VolvoCarsApi(
        web_session,
        auth,
        entry.data[CONF_VIN],
        entry.data[CONF_API_KEY],
    )

    # Setup entry
    coordinator = VolvoDataCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = VolvoData(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VolvoConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("%s - Unloading entry", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
