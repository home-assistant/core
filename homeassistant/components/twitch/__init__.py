"""The Twitch component."""

from __future__ import annotations

from typing import cast

from aiohttp.client_exceptions import ClientError, ClientResponseError
from twitchAPI.twitch import Twitch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    LocalOAuth2Implementation,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import DOMAIN, OAUTH_SCOPES, PLATFORMS
from .coordinator import TwitchConfigEntry, TwitchCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: TwitchConfigEntry) -> bool:
    """Set up Twitch from a config entry."""
    try:
        implementation = cast(
            LocalOAuth2Implementation,
            await async_get_config_entry_implementation(hass, entry),
        )
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err
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

    access_token = entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
    client = Twitch(
        app_id=implementation.client_id,
        authenticate_app=False,
    )
    client.auto_refresh_auth = False
    await client.set_user_authentication(access_token, scope=OAUTH_SCOPES)

    coordinator = TwitchCoordinator(hass, client, session, entry)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: TwitchConfigEntry) -> None:
    # Don't reload integration while we're still setting up or unloading
    if entry.state is not ConfigEntryState.LOADED:
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TwitchConfigEntry) -> bool:
    """Unload Twitch config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
