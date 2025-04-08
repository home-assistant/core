"""The Volvo integration."""

from __future__ import annotations

import logging

from volvocarsapi.api import VolvoCarsApi

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .api import VolvoAuth
from .const import CONF_VIN, PLATFORMS
from .coordinator import VolvoConfigEntry, VolvoData, VolvoDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: VolvoConfigEntry) -> bool:
    """Set up Volvo from a config entry."""
    _LOGGER.debug("%s - Loading entry", entry.entry_id)

    # Create APIs
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    web_session = aiohttp_client.async_get_clientsession(hass)

    auth = VolvoAuth(web_session, oauth_session)
    api = VolvoCarsApi(
        web_session,
        auth,
        entry.data.get(CONF_VIN, ""),
        entry.data.get(CONF_API_KEY, ""),
    )

    # Setup entry
    coordinator = VolvoDataCoordinator(hass, entry, api)
    entry.runtime_data = VolvoData(coordinator)
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register events
    entry.async_on_unload(entry.add_update_listener(_entry_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VolvoConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("%s - Unloading entry", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _entry_update_listener(hass: HomeAssistant, entry: VolvoConfigEntry) -> None:
    """Reload entry after config changes."""
    await hass.config_entries.async_reload(entry.entry_id)
