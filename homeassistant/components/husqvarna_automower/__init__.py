"""The Husqvarna Automower integration."""

import logging

from aioautomower.session import AutomowerSession
from aiohttp import ClientResponseError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.util import dt as dt_util

from . import api
from .coordinator import AutomowerConfigEntry, AutomowerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.DEVICE_TRACKER,
    Platform.LAWN_MOWER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: AutomowerConfigEntry) -> bool:
    """Set up this integration using UI."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    api_api = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass),
        session,
    )
    time_zone_str = str(dt_util.DEFAULT_TIME_ZONE)
    automower_api = AutomowerSession(
        api_api,
        await dt_util.async_get_time_zone(time_zone_str),
    )
    try:
        await api_api.async_get_access_token()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err

    if "amc:api" not in entry.data["token"]["scope"]:
        # We raise ConfigEntryAuthFailed here because the websocket can't be used
        # without the scope. So only polling would be possible.
        raise ConfigEntryAuthFailed

    coordinator = AutomowerDataUpdateCoordinator(hass, entry, automower_api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_create_background_task(
        hass,
        coordinator.client_listen(hass, entry, automower_api),
        "websocket_task",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AutomowerConfigEntry) -> bool:
    """Handle unload of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
