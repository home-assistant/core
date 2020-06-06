"""OpenID based authentication provider."""

import logging
import re
from secrets import token_hex
from typing import Any, Dict, Optional, cast

from aiohttp import ClientResponseError
from aiohttp.client import ClientResponse
import voluptuous as vol
from yarl import URL

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AUTH_CALLBACK_PATH,
    _encode_jwt,
    async_register_view,
)
from homeassistant.helpers.network import get_url

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

REQUIREMENTS = ["python-jose==3.1.0"]

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_CONFIGURATION = "configuration"
CONF_EMAILS = "emails"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_CONFIGURATION): str,
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_EMAILS): [str],
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


@AUTH_PROVIDERS.register("openid")
class OpenIdAuthProvider(AuthProvider):
    """Example auth provider based on hardcoded usernames and passwords."""

    DEFAULT_TITLE = "OpenID Connect"

    _configuration: Dict[str, Any]
    _jwks: Dict[str, Any]

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

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        url = URL(get_url(self.hass, prefer_external=True, allow_cloud=False))
        return str(url.with_path(AUTH_CALLBACK_PATH))

    async def async_login_flow(self, context: Optional[Dict]) -> LoginFlow:
        """Return a flow to login."""

        if not hasattr(self, "_configuration"):
            self._configuration = await self.async_get_configuration()

        if not hasattr(self, "_jwks"):
            self._jwks = await self.async_get_jwks()

        async_register_view(self.hass)

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

        session = async_get_clientsession(self.hass)
        async with session.post(
            self._configuration["token_endpoint"], data=payload
        ) as response:
            await raise_for_status(response)
            return cast(Dict[str, Any], await response.json())

    async def async_validate_token(
        self, token: Dict[str, Any], nonce: str
    ) -> Dict[str, Any]:
        """Validate a token."""
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

        if id_token["email"] not in self.config[CONF_EMAILS]:
            raise InvalidAuthError(f"Email {id_token['email']} not in allowed users")

        if not id_token["email_verified"]:
            raise InvalidAuthError(f"Email {id_token['email']} must be verified")

        return id_token

    async def async_generate_authorize_url(self, flow_id: str, nonce: str) -> str:
        """Generate a authorization url for a given flow."""
        scopes = WANTED_SCOPES.intersection(self._configuration["scopes_supported"])

        query = {
            "response_type": "code",
            "client_id": self.config["client_id"],
            "redirect_uri": self.redirect_uri,
            "state": _encode_jwt(self.hass, {"flow_id": flow_id, "flow_type": "login"}),
            "scope": " ".join(sorted(scopes)),
            "nonce": nonce,
        }

        return str(URL(self._configuration["authorization_endpoint"]).with_query(query))

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
            email = credentials.data["email"]
            match = re.match(r"[^@]+", email)
            if match:
                name = str(match.group(0))
            else:
                name = str(email)
        else:
            name = credentials.data["sub"]

        return UserMeta(name=name, is_active=True)


class OpenIdLoginFlow(LoginFlow):
    """Handler for the login flow."""

    external_data: str
    nonce: str

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
        self.nonce = token_hex()
        url = await provider.async_generate_authorize_url(self.flow_id, self.nonce)
        return self.async_external_step(step_id="authenticate", url=url)

    async def async_step_authorize(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Authorize user received from external step."""

        provider = cast(OpenIdAuthProvider, self._auth_provider)
        try:
            token = await provider.async_retrieve_token(self.external_data)
            result = await provider.async_validate_token(token, self.nonce)
        except InvalidAuthError as error:
            _LOGGER.error("Login failed: %s", str(error))
            return self.async_abort(reason="invalid_auth")
        return await self.async_finish(result)
