"""The Twitch component."""
from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientError, ClientResponseError
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch, TwitchUser

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import CONF_CHANNELS, DOMAIN, OAUTH_SCOPES, PLATFORMS
from .coordinator import TwitchUpdateCoordinator, chunk_list

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

    if (user := await first(client.get_users())) is None:
        raise ConfigEntryNotReady("No user found from Twitch API")

    channel_options: list[str] = entry.options[CONF_CHANNELS]

    entity_registry = er.async_get(hass)

    enabled_channels: list[TwitchUser] = []
    # Split channels into chunks of 100 to avoid hitting the rate limit
    for chunk in chunk_list(channel_options, 100):
        async for channel in client.get_users(logins=chunk):
            # Check if the entity is disabled
            if (
                entity := entity_registry.async_get(
                    f"sensor.{channel.display_name.lower()}"
                )
            ) is not None and entity.disabled:
                _LOGGER.debug(
                    "Channel %s is disabled",
                    channel.display_name,
                )
                continue
            enabled_channels.append(channel)

    _LOGGER.debug("Enabled channels: %s", len(enabled_channels))

    # Create shared channel update coordinator
    coordinator = TwitchUpdateCoordinator(
        hass,
        _LOGGER,
        client,
        user,
        enabled_channels,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Set data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Twitch config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
