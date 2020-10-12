"""OpenID based authentication provider."""

import logging
from secrets import token_hex
from typing import Any, Dict, Optional, cast

from aiohttp import ClientResponseError
from aiohttp.client import ClientResponse
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2Implementation,
    async_register_view,
)

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

REQUIREMENTS = ["python-jose==3.1.0"]

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_CONFIGURATION = "configuration"
CONF_EMAILS = "emails"
CONF_SUBJECTS = "subjects"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_CONFIGURATION): str,
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Optional(CONF_EMAILS): [str],
        vol.Optional(CONF_SUBJECTS): [str],
    },
    extra=vol.PREVENT_EXTRA,
)

OPENID_CONFIGURATION_SCHEMA = vol.Schema(
    {
        vol.Required("issuer"): str,
        vol.Required("jwks_uri"): str,
        vol.Required("id_token_signing_alg_values_supported"): list,
        vol.Optional("scopes_supported"): vol.Contains("openid"),
        vol.Required("token_endpoint"): str,
        vol.Required("authorization_endpoint"): str,
        vol.Required("response_types_supported"): vol.Contains("code"),
        vol.Optional(
            "token_endpoint_auth_methods_supported", default=["client_secret_basic"]
        ): vol.Contains("client_secret_post"),
        vol.Optional(
            "grant_types_supported", default=["authorization_code", "implicit"]
        ): vol.Contains("authorization_code"),
    },
    extra=vol.ALLOW_EXTRA,
)


class InvalidAuthError(HomeAssistantError):
    """Raised when submitting invalid authentication."""


async def raise_for_status(response: ClientResponse) -> None:
    """Raise exception on data failure with logging."""
    if response.status >= 400:
        standard = ClientResponseError(
            response.request_info,
            response.history,
            code=response.status,
            headers=response.headers,
        )
        data = await response.text()
        _LOGGER.error("Request failed: %s", data)
        raise InvalidAuthError(data) from standard


WANTED_SCOPES = {"openid", "email", "profile"}


class OpenIdLocalOAuth2Implementation(LocalOAuth2Implementation):
    """Local OAuth2 implementation for Toon."""

    _nonce: Optional[str] = None
    _scope: str

    def __init__(
        self,
        hass: HomeAssistant,
        client_id: str,
        client_secret: str,
        configuration: Dict[str, Any],
    ):
        """Initialize local auth implementation."""
        super().__init__(
            hass,
            "auth",
            client_id,
            client_secret,
            configuration["authorization_endpoint"],
            configuration["token_endpoint"],
            "login",
        )

        self._scope = " ".join(
            sorted(WANTED_SCOPES.intersection(configuration["scopes_supported"]))
        )

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": self._scope, "nonce": self._nonce}

    async def async_generate_authorize_url_with_nonce(
        self, flow_id: str, nonce: str
    ) -> str:
        """Generate an authorize url with a given nonce."""
        self._nonce = nonce
        url = await self.async_generate_authorize_url(flow_id)
        self._nonce = None
        return url


@AUTH_PROVIDERS.register("openid")
class OpenIdAuthProvider(AuthProvider):
    """Auth provider using openid connect as the authentication source."""

    DEFAULT_TITLE = "OpenID Connect"

    _configuration: Dict[str, Any]
    _jwks: Dict[str, Any]
    _oauth2: OpenIdLocalOAuth2Implementation

    async def async_get_configuration(self) -> Dict[str, Any]:
        """Get discovery document for OpenID."""
        session = async_get_clientsession(self.hass)
        async with session.get(self.config[CONF_CONFIGURATION]) as response:
            await raise_for_status(response)
            data = await response.json()
        return cast(Dict[str, Any], OPENID_CONFIGURATION_SCHEMA(data))

    async def async_get_jwks(self) -> Dict[str, Any]:
        """Get the keys for id verification."""
        session = async_get_clientsession(self.hass)
        async with session.get(self._configuration["jwks_uri"]) as response:
            await raise_for_status(response)
            data = await response.json()
        return cast(Dict[str, Any], data)

    async def async_login_flow(self, context: Optional[Dict]) -> LoginFlow:
        """Return a flow to login."""

        if not hasattr(self, "_configuration"):
            self._configuration = await self.async_get_configuration()

        if not hasattr(self, "_jwks"):
            self._jwks = await self.async_get_jwks()

        self._oauth2 = OpenIdLocalOAuth2Implementation(
            self.hass,
            self.config[CONF_CLIENT_ID],
            self.config[CONF_CLIENT_SECRET],
            self._configuration,
        )

        async_register_view(self.hass)

        return OpenIdLoginFlow(self)

    def _decode_id_token(self, token: Dict[str, Any], nonce: str) -> Dict[str, Any]:
        """Decode openid id_token."""
        from jose import jwt  # noqa: pylint: disable=import-outside-toplevel

        algorithms = self._configuration["id_token_signing_alg_values_supported"]
        issuer = self._configuration["issuer"]

        id_token = cast(
            Dict[str, Any],
            jwt.decode(
                token["id_token"],
                algorithms=algorithms,
                issuer=issuer,
                key=self._jwks,
                audience=self.config[CONF_CLIENT_ID],
                access_token=token["access_token"],
            ),
        )
        if id_token.get("nonce") != nonce:
            raise InvalidAuthError("Nonce mismatch in id_token")

        return id_token

    def _authorize_id_token(self, id_token: Dict[str, Any]) -> Dict[str, Any]:
        """Authorize an id_token according to our internal database."""

        if id_token["sub"] in self.config.get(CONF_SUBJECTS, []):
            return id_token

        if "email" in id_token and "email_verified" in id_token:
            if (
                id_token["email"] in self.config.get(CONF_EMAILS, [])
                and id_token["email_verified"]
            ):
                return id_token

        raise InvalidAuthError(f"Subject {id_token['sub']} is not allowed")

    async def async_generate_authorize_url_with_nonce(
        self, flow_id: str, nonce: str
    ) -> str:
        """Generate an authorize url with a given nonce."""
        return await self._oauth2.async_generate_authorize_url_with_nonce(
            flow_id, nonce
        )

    async def async_authorize_external_data(
        self, external_data: str, nonce: str
    ) -> Dict[str, Any]:
        """Authorize external data."""
        token = await self._oauth2.async_resolve_external_data(external_data)
        id_token = self._decode_id_token(token, nonce)
        return self._authorize_id_token(id_token)

    @property
    def support_mfa(self) -> bool:
        """Return whether multi-factor auth supported by the auth provider."""
        return False

    async def async_get_or_create_credentials(
        self, flow_result: Dict[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        subject = flow_result["sub"]

        for credential in await self.async_credentials():
            if credential.data["sub"] == subject:
                _LOGGER.info("Accepting credential for %s", subject)
                return credential

        _LOGGER.info("Creating credential for %s", subject)
        return self.async_create_credentials(flow_result)

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.
        """
        if "preferred_username" in credentials.data:
            name = credentials.data["preferred_username"]
        elif "given_name" in credentials.data:
            name = credentials.data["given_name"]
        elif "name" in credentials.data:
            name = credentials.data["name"]
        elif "email" in credentials.data:
            name = cast(str, credentials.data["email"]).split("@", 1)[0]
        else:
            name = credentials.data["sub"]

        return UserMeta(name=name, is_active=True)


class OpenIdLoginFlow(LoginFlow):
    """Handler for the login flow."""

    external_data: str
    _nonce: str

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

        self._nonce = token_hex()
        url = await provider.async_generate_authorize_url_with_nonce(
            self.flow_id, self._nonce
        )
        return self.async_external_step(step_id="authenticate", url=url)

    async def async_step_authorize(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Authorize user received from external step."""

        provider = cast(OpenIdAuthProvider, self._auth_provider)
        try:
            result = await provider.async_authorize_external_data(
                self.external_data, self._nonce
            )
        except InvalidAuthError as error:
            _LOGGER.error("Login failed: %s", str(error))
            return self.async_abort(reason="invalid_auth")
        return await self.async_finish(result)
