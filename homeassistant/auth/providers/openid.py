"""OpenId based authentication provider."""

import logging
import re
from typing import Any, Dict, Optional, cast

from aiohttp.web import HTTPBadRequest, Request, Response
import jwt
import voluptuous as vol
from yarl import URL

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import _decode_jwt, _encode_jwt

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_TOKEN_URI = "token_uri"
CONF_AUTHORIZATION_URI = "authorization_uri"
CONF_EMAILS = "emails"

DATA_JWT_SECRET = "openid_jwt_secret"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_TOKEN_URI): str,
        vol.Required(CONF_AUTHORIZATION_URI): str,
        vol.Required(CONF_EMAILS): [str],
    },
    extra=vol.PREVENT_EXTRA,
)

AUTH_CALLBACK_PATH = "/api/openid/redirect"


class InvalidAuthError(HomeAssistantError):
    """Raised when submitting invalid authentication."""


registered = False


@AUTH_PROVIDERS.register("openid")
class OpenIdAuthProvider(AuthProvider):
    """Example auth provider based on hardcoded usernames and passwords."""

    DEFAULT_TITLE = "OpenId Connect"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Extend parent's __init__."""
        super().__init__(*args, **kwargs)

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return f"{self.hass.config.api.base_url}{AUTH_CALLBACK_PATH}"  # type: ignore

    async def async_login_flow(self, context: Optional[Dict]) -> LoginFlow:
        """Return a flow to login."""
        global registered
        if not registered:
            self.hass.http.register_view(OpenIdCallbackView())  # type: ignore
        registered = True
        return OpenIdLoginFlow(self)

    async def async_retrieve_token(self, code: str) -> Dict[str, Any]:
        """Convert a token code into an actual token."""
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.config[CONF_CLIENT_ID],
            "client_secret": self.config[CONF_CLIENT_SECRET],
        }
        uri = self.config[CONF_TOKEN_URI]
        session = async_get_clientsession(self.hass)

        async with session.post(uri, data=payload) as response:
            if 400 <= response.status:
                if "json" in response.headers.get("CONTENT-TYPE", ""):
                    data = await response.json()
                else:
                    data = await response.text()
                raise InvalidAuthError(f"Token validation failed with error: {data}")
            return cast(Dict[str, Any], await response.json())

    async def async_validate_token(self, token: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a token."""
        id_token = jwt.decode(token["id_token"])

        if id_token["email"] not in self.config[CONF_EMAILS]:
            raise InvalidAuthError(f"Email {id_token['email']} not in allowed users")
        return id_token

    @callback
    def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a authorization url for a given flow."""
        return str(
            URL(self.config["authorization_uri"]).with_query(
                {
                    "response_type": "code",
                    "client_id": self.config["client_id"],
                    "redirect_uri": self.redirect_uri,
                    "state": _encode_jwt(self.hass, {"flow_id": flow_id}),
                    "scope": "openid email",
                }
            )
        )

    async def async_get_or_create_credentials(
        self, flow_result: Dict[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        email = flow_result["email"]

        for credential in await self.async_credentials():
            if credential.data["email"] == email:
                return credential

        # Create new credentials.
        return self.async_create_credentials(flow_result)

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.
        """
        email = credentials.data["email"]
        match = re.match(r"([^@]+)", email)
        if match:
            name = str(match.groups(0))
        else:
            name = str(email)

        return UserMeta(name=name, is_active=True)


class OpenIdLoginFlow(LoginFlow):
    """Handler for the login flow."""

    external_data: str

    async def async_step_init(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Handle the step of the form."""
        return await self.async_step_authenticate()

    async def async_step_authenticate(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Authenticate user using external step."""

        provider = cast(OpenIdAuthProvider, self._auth_provider)

        if user_input:
            self.external_data = str(user_input)
            return self.async_external_step_done(next_step_id="authorize")

        url = provider.async_generate_authorize_url(self.flow_id)
        return self.async_external_step(step_id="authenticate", url=url)

    async def async_step_authorize(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Authorize user received from external step."""

        provider = cast(OpenIdAuthProvider, self._auth_provider)
        try:
            token = await provider.async_retrieve_token(self.external_data)
            result = await provider.async_validate_token(token)
        except InvalidAuthError:
            return self.async_abort(reason="invalid_auth")
        return await self.async_finish(result)


class OpenIdCallbackView(HomeAssistantView):
    """Handle openid callback."""

    url = AUTH_CALLBACK_PATH
    name = "api:openid:redirect"
    requires_auth = False

    def __init__(self) -> None:
        """Initialize instance of the view."""
        super().__init__()

    async def get(self, request: Request) -> Response:
        """Handle oauth token request."""
        hass = cast(HomeAssistant, request.app["hass"])

        def check_get(param: str) -> Any:
            if param not in request.query:
                _LOGGER.error("State missing in request.")
                raise HTTPBadRequest(text="Parameter {} not found".format(param))
            return request.query[param]

        state = check_get("state")
        code = check_get("code")

        state = _decode_jwt(hass, state)
        if state is None:
            _LOGGER.error("State failed to decode.")
            raise HTTPBadRequest(text="Invalid state")

        auth_manager = hass.auth  # type: ignore
        await auth_manager.login_flow.async_configure(state["flow_id"], user_input=code)

        return Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>",
        )
