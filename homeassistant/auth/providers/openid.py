"""OpenId based authentication provider."""

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

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

REQUIREMENTS = ["python-jose==3.1.0"]

_LOGGER = logging.getLogger(__name__)

CONF_ISSUER = "issuer"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_TOKEN_URI = "token_uri"
CONF_AUTHORIZATION_URI = "authorization_uri"
CONF_EMAILS = "emails"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_ISSUER): str,
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_EMAILS): [str],
    },
    extra=vol.PREVENT_EXTRA,
)

OPENID_CONFIGURATION_PATH = ".well-known/openid-configuration"


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

    DEFAULT_TITLE = "OpenId Connect"

    _discovery_document: Dict[str, Any]
    _jwks: Dict[str, Any]

    async def async_get_discovery_document(self) -> None:
        """Cache discovery document for openid."""
        if hasattr(self, "._discovery_document"):
            return

        session = async_get_clientsession(self.hass)
        async with session.get(self.discovery_url) as response:
            await raise_for_status(response)
            self._discovery_document = cast(Dict[str, Any], await response.json())

    async def async_get_jwks(self) -> None:
        """Cache the keys for id verification."""
        if hasattr(self, "._jwks"):
            return

        session = async_get_clientsession(self.hass)
        async with session.get(self._discovery_document["jwks_uri"]) as response:
            await raise_for_status(response)
            self._jwks = cast(Dict[str, Any], await response.json())

    @property
    def discovery_url(self) -> str:
        """Construct discovery url based on config."""
        return str(URL(self.config[CONF_ISSUER]).with_path(OPENID_CONFIGURATION_PATH))

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return f"{self.hass.config.api.base_url}{AUTH_CALLBACK_PATH}"  # type: ignore

    async def async_login_flow(self, context: Optional[Dict]) -> LoginFlow:
        """Return a flow to login."""

        await self.async_get_discovery_document()
        await self.async_get_jwks()

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
            self._discovery_document["token_endpoint"], data=payload
        ) as response:
            await raise_for_status(response)
            return cast(Dict[str, Any], await response.json())

    async def async_validate_token(
        self, token: Dict[str, Any], nonce: str
    ) -> Dict[str, Any]:
        """Validate a token."""
        from jose import jwt

        algorithms = self._discovery_document.get(
            "id_token_signing_alg_values_supported", ["RS256"]
        )

        issuer = self._discovery_document.get("issuer", None)

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
            raise InvalidAuthError(f"Nonce mismatch in id_token")

        if id_token["email"] not in self.config[CONF_EMAILS]:
            raise InvalidAuthError(f"Email {id_token['email']} not in allowed users")
        return id_token

    async def async_generate_authorize_url(self, flow_id: str, nonce: str) -> str:
        """Generate a authorization url for a given flow."""
        scopes = WANTED_SCOPES.intersection(
            self._discovery_document["scopes_supported"]
        )

        query = {
            "response_type": "code",
            "client_id": self.config["client_id"],
            "redirect_uri": self.redirect_uri,
            "state": _encode_jwt(self.hass, {"flow_id": flow_id, "flow_type": "login"}),
            "scope": " ".join(sorted(scopes)),
            "nonce": nonce,
        }

        return str(
            URL(self._discovery_document["authorization_endpoint"]).with_query(query)
        )

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
                _LOGGER.info("Accepting credential for %s", flow_result["email"])
                return credential

        _LOGGER.info("Creating credential for %s", flow_result["email"])
        return self.async_create_credentials(flow_result)

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.
        """
        email = credentials.data["email"]
        if "name" in credentials.data:
            name = credentials.data["name"]
        else:
            match = re.match(r"[^@]+", email)
            if match:
                name = str(match.group(0))
            else:
                name = str(email)

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
        except InvalidAuthError:
            return self.async_abort(reason="invalid_auth")
        return await self.async_finish(result)
