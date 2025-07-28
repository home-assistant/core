"""API for hello auth bound to Home Assistant OAuth."""

from json import JSONDecodeError
import logging
import secrets
from typing import Any, cast

from aiohttp import ClientError
import jwt
from yarl import URL

from homeassistant.components.application_credentials import AuthImplementation
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import HOST
from .hinen import HinenOpen
from .util import RespUtil

_LOGGER = logging.getLogger(__name__)


class AsyncConfigEntryAuth:
    """Provide Hinen authentication tied to an OAuth2 based config entry."""

    hinen_open: HinenOpen | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        oauth2_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize YouTube Auth."""
        self.oauth_session = oauth2_session
        self.hass = hass

    @property
    def access_token(self) -> str:
        """Return the access token."""
        return self.oauth_session.token[CONF_ACCESS_TOKEN]  # type: ignore[no-any-return]

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

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize."""
        redirect_uri = self.redirect_uri
        url = self.authorize_url
        language = "en_US"
        key = self.client_id
        redirectUrl = "https://my.home-assistant.io/redirect/oauth"
        if (
            secret := self.hass.data.get(config_entry_oauth2_flow.DATA_JWT_SECRET)
        ) is None:
            secret = self.hass.data[config_entry_oauth2_flow.DATA_JWT_SECRET] = (
                secrets.token_hex()
            )

        state = jwt.encode(
            {"flow_id": flow_id, "redirect_uri": redirect_uri},
            secret,
            algorithm="HS256",
        )

        return f"{url}?&state={state}&language={language}&key={key}&redirectUrl={redirectUrl}"

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        _LOGGER.info("Sending token request to %s", external_data)
        request_data: dict = {
            "clientSecret": self.client_secret,
            "grantType": "1",
            "authorizationCode": external_data["code"],
            "regionCode": "CN",
        }
        request_data.update(self.extra_token_resolve_data)
        return await self._token_request(request_data)

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        new_token = await self._token_request(
            {
                "grant_type": "2",
                "clientSecret": self.client_secret,
                "regionCode": "CN",
                "refreshToken": token["refresh_token"],
            }
        )
        return {**token, **new_token}

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)
        url = str(URL(self.token_url).with_query(data))
        _LOGGER.debug("Sending token request to %s", self.token_url)

        resp = await session.get(url)
        if resp.status >= 400:
            try:
                error_response = await resp.json()
            except (ClientError, JSONDecodeError):
                error_response = {}
            error_code = error_response.get("error", "unknown")
            error_description = error_response.get("error_description", "unknown error")
            _LOGGER.error(
                "Token request for %s failed (%s): %s",
                self.domain,
                error_code,
                error_description,
            )
        resp.raise_for_status()
        custom_token = cast(dict[str, Any], await resp.json())
        _LOGGER.debug("resp: %s", custom_token)

        return RespUtil.convert_to_snake_case(custom_token.get("data", {}))
