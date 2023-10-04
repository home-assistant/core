"""The Twitch component."""
from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientError, ClientResponseError
from twitchAPI.twitch import Twitch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import DOMAIN, OAUTH_SCOPES, PLATFORMS
from .coordinator import TwitchUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twitch from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    app_id = implementation.__dict__[CONF_CLIENT_ID]
    access_token = entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
    client = await Twitch(
        app_id=app_id,
        authenticate_app=False,
    )
    client.auto_refresh_auth = False
    await client.set_user_authentication(access_token, scope=OAUTH_SCOPES)

    coordinator = TwitchUpdateCoordinator(
        hass,
        _LOGGER,
        client,
        entry.options,
    )

    # Set data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Twitch config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
