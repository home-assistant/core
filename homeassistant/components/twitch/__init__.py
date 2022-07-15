"""The Twitch integration."""
from __future__ import annotations

import logging

from twitchAPI.twitch import Twitch, TwitchAPIException, TwitchBackendException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CONF_REFRESH_TOKEN, DOMAIN, OAUTH_SCOPES

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []
# PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twitch from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    await session.async_ensure_token_valid()

    client_id = entry.data["auth_implementation"].split("_")[1]
    access_token = entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
    refresh_token = entry.data[CONF_TOKEN][CONF_REFRESH_TOKEN]

    client = Twitch(
        app_id=client_id,
        authenticate_app=False,
        target_app_auth_scope=OAUTH_SCOPES,
    )
    client.auto_refresh_auth = False

    await hass.async_add_executor_job(
        client.set_user_authentication,
        access_token,
        OAUTH_SCOPES,
        refresh_token,
        True,
    )

    # Set data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client
    # hass.data[DOMAIN][entry.entry_id] = coordinator

    try:
        users = await hass.async_add_executor_job(client.get_users)
    except (TwitchAPIException, TwitchBackendException) as err:
        raise ConfigEntryNotReady from err

    _LOGGER.debug("User: %s", users["data"][0])

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
