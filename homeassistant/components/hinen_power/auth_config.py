"""Authentication for Hinen Power using Home Assistant OAuth2."""

from json import JSONDecodeError
import logging
from typing import Any, cast

from aiohttp import ClientError
from hinen_open_api import HinenOpen
from hinen_open_api.utils import RespUtil
from yarl import URL

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTR_REGION_CODE, HOST, REGION_CODE

_LOGGER = logging.getLogger(__name__)


class AsyncConfigEntryAuth:
    """Provide Hinen authentication tied to an OAuth2 based config entry."""

    hinen_open: HinenOpen | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        oauth2_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Hinen Auth."""
        self.oauth_session = oauth2_session
        self.hass = hass

    @property
    def access_token(self) -> str:
        """Return the access token."""
        return self.oauth_session.token[CONF_ACCESS_TOKEN]

    async def check_and_refresh_token(self) -> str:
        """Check the token."""
        await self.oauth_session.async_ensure_token_valid()
        return self.access_token

    async def get_resource(self) -> HinenOpen:
        """Create resource."""
        token = await self.check_and_refresh_token()
        if self.hinen_open is None:
            self.hinen_open = HinenOpen(
                self.oauth_session.token[HOST],
                session=async_get_clientsession(self.hass),
            )
        await self.hinen_open.set_user_authentication(token)
        return self.hinen_open


class HinenImplementation(AuthImplementation):
    """Hinen implementation of LocalOAuth2Implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_credential: ClientCredential,
        authorization_server: AuthorizationServer,
        language: str | None = None,
        region_code: str | None = None,
    ) -> None:
        """Set up Hinen OAuth2 implementation."""
        super().__init__(
            hass=hass,
            auth_domain=domain,
            credential=client_credential,
            authorization_server=authorization_server,
        )

        self._language = language
        self._region_code = region_code
        self._name = client_credential.name

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize."""
        # Get standard authorization URL from parent class
        standard_url = await super().async_generate_authorize_url(flow_id)

        # Extract state from standard URL
        state = URL(standard_url).query.get("state")
        return f"{self.authorize_url}?state={state}&language={self._language}&key={self.client_id}&redirectUrl={self.redirect_uri}"

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        request_data: dict = {
            "clientSecret": self.client_secret,
            "grantType": "1",
            "authorizationCode": external_data["code"],
            "regionCode": self._region_code,
        }
        request_data.update(self.extra_token_resolve_data)
        return await self._token_request(request_data)

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        new_token = await self._token_request(
            {
                "grantType": "2",
                "clientSecret": self.client_secret,
                "regionCode": token.get(ATTR_REGION_CODE),
                "refreshToken": token["refresh_token"],
            }
        )
        return {**token, **new_token}

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)
        url = str(URL(self.token_url).with_query(data))
        _LOGGER.debug("Sending token request to %s", self.token_url)

        async with session.get(url) as resp:
            if resp.status >= 400:
                try:
                    error_response = await resp.json()
                except ClientError, JSONDecodeError:
                    error_response = {}
                error_code = error_response.get("code", "unknown")
                error_description = error_response.get("msg", "unknown error")
                error_trace_id = error_response.get("traceId", "unknown error")
                _LOGGER.error(
                    "Token request for %s failed (%s): %s traceId:%s",
                    self.domain,
                    error_code,
                    error_description,
                    error_trace_id,
                )
            resp.raise_for_status()
            custom_token = cast(dict[str, Any], await resp.json()).get("data", {})
            custom_token.update(
                {
                    "clientId": self.client_id,
                    "clientSecret": self.client_secret,
                    REGION_CODE: data.get(REGION_CODE),
                }
            )
        return RespUtil.convert_to_snake_case(custom_token)
