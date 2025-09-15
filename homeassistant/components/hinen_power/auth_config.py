"""API for hello auth bound to Home Assistant OAuth."""

from json import JSONDecodeError
import logging
import secrets
from typing import Any, cast

from aiohttp import ClientError, web
from hinen_open_api import HinenOpen
from hinen_open_api.utils import RespUtil
import jwt
from yarl import URL

from homeassistant.components.application_credentials import AuthImplementation
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, http
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_AUTH_LANGUAGE,
    ATTR_CLIENT_SECRET,
    ATTR_REDIRECTION_URL,
    ATTR_REGION_CODE,
    CLIENT_SECRET,
    HOST,
    REGION_CODE,
)

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

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize."""
        redirect_uri = self.redirect_uri
        url = self.authorize_url
        language = self.hass.data[ATTR_AUTH_LANGUAGE]
        key = self.client_id
        redirectUrl = f"{self.hass.data[ATTR_REDIRECTION_URL]}/auth/hinen/callback"
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
            "clientSecret": external_data[ATTR_CLIENT_SECRET],
            "grantType": "1",
            "authorizationCode": external_data["code"],
            "regionCode": external_data[ATTR_REGION_CODE],
        }
        request_data.update(self.extra_token_resolve_data)
        return await self._token_request(request_data)

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        new_token = await self._token_request(
            {
                "grantType": "2",
                "clientSecret": token.get(ATTR_CLIENT_SECRET),
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

        resp = await session.get(url)
        if resp.status >= 400:
            try:
                error_response = await resp.json()
            except (ClientError, JSONDecodeError):
                error_response = {}
            error_code = error_response.get("code", "unknown")
            error_description = error_response.get("msg", "unknown error")
            error_trace_id = error_response.get("traceId", "unknown error")
            _LOGGER.error(
                "Token request for %s failed (%s): %s tranceId:%s",
                self.domain,
                error_code,
                error_description,
                error_trace_id,
            )
        resp.raise_for_status()
        custom_token = cast(dict[str, Any], await resp.json()).get("data", {})
        custom_token.update(
            {
                CLIENT_SECRET: data.get(CLIENT_SECRET),
                REGION_CODE: data.get(REGION_CODE),
            }
        )

        _LOGGER.debug("resp: %s", custom_token)
        return RespUtil.convert_to_snake_case(custom_token)


class HinenOAuth2AuthorizeCallbackView(http.HomeAssistantView):
    """OAuth2 Authorization Callback View."""

    url = "/auth/hinen/callback"
    name = "auth:hinen:callback"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Receive authorization code."""
        if "state" not in request.query:
            return web.Response(text="Missing state parameter")

        hass = request.app[http.KEY_HASS]

        state = _decode_jwt(hass, request.query["state"])

        if state is None:
            return web.Response(
                text=(
                    "Invalid state. Is My Home Assistant configured "
                    "to go to the right instance?"
                ),
                status=400,
            )

        user_input: dict[str, Any] = {
            "state": state,
            ATTR_REGION_CODE: request.query[REGION_CODE],
            ATTR_CLIENT_SECRET: request.query[CLIENT_SECRET],
        }
        if "code" in request.query:
            user_input["code"] = request.query["code"]
        elif "error" in request.query:
            user_input["error"] = request.query["error"]
        else:
            return web.Response(text="Missing code or error parameter")

        await hass.config_entries.flow.async_configure(
            flow_id=state["flow_id"], user_input=user_input
        )
        _LOGGER.debug("Resumed OAuth configuration flow")
        return web.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>",
        )


def _decode_jwt(hass: HomeAssistant, encoded: str) -> dict[str, Any] | None:
    """JWT encode data."""
    secret: str | None = hass.data.get(config_entry_oauth2_flow.DATA_JWT_SECRET)

    if secret is None:
        return None

    try:
        return jwt.decode(encoded, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
