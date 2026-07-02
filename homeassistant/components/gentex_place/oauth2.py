"""API for place bound to Home Assistant OAuth."""

import logging
import time
from typing import cast, override

from aiohttp import ClientSession
from place.auth.abstract_auth import AbstractAuth
from place.config import COGNITO_CLIENT_ID, OAUTH2_TOKEN_URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class SRPAuthImplementation(config_entry_oauth2_flow.AbstractOAuth2Implementation):
    """Base class to abstract OAuth2 authentication."""

    def __init__(self, hass: HomeAssistant, domain: str) -> None:
        """Initialize the SRP Auth implementation."""

        self.hass = hass
        self._domain = domain
        self.client_id = COGNITO_CLIENT_ID

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return "SRPAuth"

    @property
    @override
    def domain(self) -> str:
        """Domain that is providing the implementation."""
        return self._domain

    @override
    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Left intentionally blank because the auth is handled by SRP."""
        return ""

    @override
    async def async_resolve_external_data(self, external_data) -> dict:
        """Format the token from the source appropriately for HomeAssistant."""
        auth_result = external_data["tokens"]["AuthenticationResult"]
        return {
            "access_token": auth_result["AccessToken"],
            "refresh_token": auth_result["RefreshToken"],
            "token_type": auth_result["TokenType"],
            "expires_in": auth_result["ExpiresIn"],
            "expires_at": time.time() + auth_result["ExpiresIn"],
            "id_token": auth_result["IdToken"],
        }

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)

        data["client_id"] = self.client_id

        _LOGGER.debug("Sending token request to %s", OAUTH2_TOKEN_URL)
        resp = await session.post(OAUTH2_TOKEN_URL, data=data)
        resp.raise_for_status()
        return cast(dict, await resp.json())

    @override
    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        new_token = await self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token["refresh_token"],
            }
        )
        return {**token, **new_token}


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide place authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize place auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]
