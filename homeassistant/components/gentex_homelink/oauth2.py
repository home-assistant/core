"""API for homelink bound to Home Assistant OAuth."""

from json import JSONDecodeError
import logging
import time
from typing import cast

from aiohttp import ClientError, ClientSession
from homelink.auth.abstract_auth import AbstractAuth
from homelink.settings import COGNITO_CLIENT_ID

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import OAUTH2_TOKEN

_LOGGER = logging.getLogger(__name__)


class SRPAuthImplementation(config_entry_oauth2_flow.AbstractOAuth2Implementation):
    """Base class to abstract OAuth2 authentication."""

    def __init__(self, hass: HomeAssistant, domain) -> None:
        """Initialize the SRP Auth implementation."""

        self.hass = hass
        self._domain = domain
        self.client_id = COGNITO_CLIENT_ID

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "SRPAuth"

    @property
    def domain(self) -> str:
        """Domain that is providing the implementation."""
        return self._domain

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Left intentionally blank because the auth is handled by SRP."""
        return ""

    async def async_resolve_external_data(self, external_data) -> dict:
        """Format the token from the source appropriately for HomeAssistant."""
        tokens = external_data["tokens"]
        new_token = {}
        new_token["access_token"] = tokens["AuthenticationResult"]["AccessToken"]
        new_token["refresh_token"] = tokens["AuthenticationResult"]["RefreshToken"]
        new_token["token_type"] = tokens["AuthenticationResult"]["TokenType"]
        new_token["expires_in"] = tokens["AuthenticationResult"]["ExpiresIn"]
        new_token["expires_at"] = (
            time.time() + tokens["AuthenticationResult"]["ExpiresIn"]
        )

        return new_token

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)

        data["client_id"] = self.client_id

        _LOGGER.debug("Sending token request to %s", OAUTH2_TOKEN)
        resp = await session.post(OAUTH2_TOKEN, data=data)
        if resp.status >= 400:
            try:
                error_response = await resp.json()
            except (ClientError, JSONDecodeError):
                error_response = {}
                error_code = error_response.get("error", "unknown")
                error_description = error_response.get(
                    "error_description", "unknown error"
                )
                _LOGGER.error(
                    "Token request for %s failed (%s): %s",
                    self.domain,
                    error_code,
                    error_description,
                )
        resp.raise_for_status()
        return cast(dict, await resp.json())

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
    """Provide homelink authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize homelink auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]
