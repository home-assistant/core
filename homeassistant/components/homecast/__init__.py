"""The Homecast integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from pyhomecast import HomecastClient, HomecastWebSocket

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .application_credentials import authorization_server_context
from .const import (
    API_BASE_URL,
    CONF_API_URL,
    CONF_MODE,
    CONF_OAUTH_AUTHORIZE_URL,
    CONF_OAUTH_TOKEN_URL,
    DOMAIN as DOMAIN,
    MODE_COMMUNITY,
    OAUTH_AUTHORIZE_URL,
    OAUTH_TOKEN_URL,
)
from .coordinator import HomecastCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.LIGHT,
]


@dataclass
class HomecastData:
    """Runtime data for a Homecast config entry."""

    coordinator: HomecastCoordinator
    client: HomecastClient


type HomecastConfigEntry = ConfigEntry[HomecastData]


async def async_setup_entry(hass: HomeAssistant, entry: HomecastConfigEntry) -> bool:
    """Set up Homecast from a config entry."""
    mode = entry.data.get(CONF_MODE)
    api_url = entry.data.get(CONF_API_URL, API_BASE_URL)

    authorize_url = entry.data.get(CONF_OAUTH_AUTHORIZE_URL, OAUTH_AUTHORIZE_URL)
    token_url = entry.data.get(CONF_OAUTH_TOKEN_URL, OAUTH_TOKEN_URL)

    with authorization_server_context(
        AuthorizationServer(authorize_url=authorize_url, token_url=token_url)
    ):
        implementation = await async_get_config_entry_implementation(hass, entry)

    session = OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed from err
    except OAuth2TokenRequestError as err:
        raise ConfigEntryNotReady from err

    http_session = async_get_clientsession(hass)
    client = HomecastClient(session=http_session, api_url=api_url)
    client.authenticate(session.token[CONF_ACCESS_TOKEN])

    device_id = f"ha_{entry.entry_id[:12]}"
    ws = HomecastWebSocket(
        session=http_session,
        api_url=api_url,
        device_id=device_id,
        community=(mode == MODE_COMMUNITY),
    )

    async def _refresh_token() -> str:
        """Refresh the OAuth token and return the new access token."""
        await session.async_ensure_token_valid()
        token = session.token[CONF_ACCESS_TOKEN]
        client.authenticate(token)
        if ws:
            ws.set_token(token)
        return token

    coordinator = HomecastCoordinator(
        hass,
        entry,
        client,
        _refresh_token,
        ws=ws,
        initial_token=session.token[CONF_ACCESS_TOKEN],
    )

    await coordinator.async_config_entry_first_refresh()

    # Start WebSocket after initial state is available
    await coordinator.async_setup_websocket()

    entry.runtime_data = HomecastData(coordinator=coordinator, client=client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomecastConfigEntry) -> bool:
    """Unload a Homecast config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
