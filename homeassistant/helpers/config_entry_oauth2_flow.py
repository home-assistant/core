"""Config Flow using OAuth2.

This module exists of the following parts:
 - OAuth2 config flow which supports multiple OAuth2 implementations
 - OAuth2 implementation that works with local provided client ID/secret

"""
from abc import ABC, ABCMeta, abstractmethod
import asyncio
import logging
import secrets
import time
from typing import Any, Awaitable, Callable, Dict, Optional, cast

from aiohttp import client, web
import async_timeout
import jwt
import voluptuous as vol
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DATA_JWT_SECRET = "oauth2_jwt_secret"
DATA_VIEW_REGISTERED = "oauth2_view_reg"
DATA_IMPLEMENTATIONS = "oauth2_impl"
DATA_PROVIDERS = "oauth2_providers"
AUTH_CALLBACK_PATH = "/auth/external/callback"


class AbstractOAuth2Implementation(ABC):
    """Base class to abstract OAuth2 authentication."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the implementation."""

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain that is providing the implementation."""

    @abstractmethod
    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize.

        This step is called when a config flow is initialized. It should redirect the
        user to the vendor website where they can authorize Home Assistant.

        The implementation is responsible to get notified when the user is authorized
        and pass this to the specified config flow. Do as little work as possible once
        notified. You can do the work inside async_resolve_external_data. This will
        give the best UX.

        Pass external data in with:

        await hass.config_entries.flow.async_configure(
            flow_id=flow_id, user_input=external_data
        )

        """

    @abstractmethod
    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve external data to tokens.

        Turn the data that the implementation passed to the config flow as external
        step data into tokens. These tokens will be stored as 'token' in the
        config entry data.
        """

    async def async_refresh_token(self, token: dict) -> dict:
        """Refresh a token and update expires info."""
        new_token = await self._async_refresh_token(token)
        # Force int for non-compliant oauth2 providers
        new_token["expires_in"] = int(new_token["expires_in"])
        new_token["expires_at"] = time.time() + new_token["expires_in"]
        return new_token

    @abstractmethod
    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh a token."""


class LocalOAuth2Implementation(AbstractOAuth2Implementation):
    """Local OAuth2 implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        token_url: str,
    ):
        """Initialize local auth implementation."""
        self.hass = hass
        self._domain = domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.token_url = token_url

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Configuration.yaml"

    @property
    def domain(self) -> str:
        """Domain providing the implementation."""
        return self._domain

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return f"{get_url(self.hass, require_current_request=True)}{AUTH_CALLBACK_PATH}"

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {}

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize."""
        return str(
            URL(self.authorize_url)
            .with_query(
                {
                    "response_type": "code",
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "state": _encode_jwt(self.hass, {"flow_id": flow_id}),
                }
            )
            .update_query(self.extra_authorize_data)
        )

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": external_data,
                "redirect_uri": self.redirect_uri,
            }
        )

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

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)

        data["client_id"] = self.client_id

        if self.client_secret is not None:
            data["client_secret"] = self.client_secret

        resp = await session.post(self.token_url, data=data)
        resp.raise_for_status()
        return cast(dict, await resp.json())


class AbstractOAuth2FlowHandler(config_entries.ConfigFlow, metaclass=ABCMeta):
    """Handle a config flow."""

    DOMAIN = ""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    def __init__(self) -> None:
        """Instantiate config flow."""
        if self.DOMAIN == "":
            raise TypeError(
                f"Can't instantiate class {self.__class__.__name__} without DOMAIN being set"
            )

        self.external_data: Any = None
        self.flow_impl: AbstractOAuth2Implementation = None  # type: ignore

    @property
    @abstractmethod
    def logger(self) -> logging.Logger:
        """Return logger."""

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {}

    async def async_step_pick_implementation(
        self, user_input: Optional[dict] = None
    ) -> dict:
        """Handle a flow start."""
        assert self.hass
        implementations = await async_get_implementations(self.hass, self.DOMAIN)

        if user_input is not None:
            self.flow_impl = implementations[user_input["implementation"]]
            return await self.async_step_auth()

        if not implementations:
            return self.async_abort(reason="missing_configuration")

        if len(implementations) == 1:
            # Pick first implementation as we have only one.
            self.flow_impl = list(implementations.values())[0]
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="pick_implementation",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "implementation", default=list(implementations.keys())[0]
                    ): vol.In({key: impl.name for key, impl in implementations.items()})
                }
            ),
        )

    async def async_step_auth(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create an entry for auth."""
        # Flow has been triggered by external data
        if user_input:
            self.external_data = user_input
            return self.async_external_step_done(next_step_id="creation")

        try:
            with async_timeout.timeout(10):
                url = await self.flow_impl.async_generate_authorize_url(self.flow_id)
        except asyncio.TimeoutError:
            return self.async_abort(reason="authorize_url_timeout")
        except NoURLAvailableError:
            return self.async_abort(
                reason="no_url_available",
                description_placeholders={
                    "docs_url": "https://www.home-assistant.io/more-info/no-url-available"
                },
            )

        url = str(URL(url).update_query(self.extra_authorize_data))

        return self.async_external_step(step_id="auth", url=url)

    async def async_step_creation(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create config entry from external data."""
        token = await self.flow_impl.async_resolve_external_data(self.external_data)
        # Force int for non-compliant oauth2 providers
        try:
            token["expires_in"] = int(token["expires_in"])
        except ValueError as err:
            _LOGGER.warning("Error converting expires_in to int: %s", err)
            return self.async_abort(reason="oauth_error")
        token["expires_at"] = time.time() + token["expires_in"]

        self.logger.info("Successfully authenticated")

        return await self.async_oauth_create_entry(
            {"auth_implementation": self.flow_impl.domain, "token": token}
        )

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the flow.

        Ok to override if you want to fetch extra info or even add another step.
        """
        return self.async_create_entry(title=self.flow_impl.name, data=data)

    async def async_step_discovery(
        self, discovery_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a flow initialized by discovery."""
        await self.async_set_unique_id(self.DOMAIN)

        assert self.hass is not None
        if self.hass.config_entries.async_entries(self.DOMAIN):
            return self.async_abort(reason="already_configured")

        return await self.async_step_pick_implementation()

    async_step_user = async_step_pick_implementation
    async_step_mqtt = async_step_discovery
    async_step_ssdp = async_step_discovery
    async_step_zeroconf = async_step_discovery
    async_step_homekit = async_step_discovery

    @classmethod
    def async_register_implementation(
        cls, hass: HomeAssistant, local_impl: LocalOAuth2Implementation
    ) -> None:
        """Register a local implementation."""
        async_register_implementation(hass, cls.DOMAIN, local_impl)


@callback
def async_register_implementation(
    hass: HomeAssistant, domain: str, implementation: AbstractOAuth2Implementation
) -> None:
    """Register an OAuth2 flow implementation for an integration."""
    if isinstance(implementation, LocalOAuth2Implementation) and not hass.data.get(
        DATA_VIEW_REGISTERED, False
    ):
        hass.http.register_view(OAuth2AuthorizeCallbackView())  # type: ignore
        hass.data[DATA_VIEW_REGISTERED] = True

    implementations = hass.data.setdefault(DATA_IMPLEMENTATIONS, {})
    implementations.setdefault(domain, {})[implementation.domain] = implementation


async def async_get_implementations(
    hass: HomeAssistant, domain: str
) -> Dict[str, AbstractOAuth2Implementation]:
    """Return OAuth2 implementations for specified domain."""
    registered = cast(
        Dict[str, AbstractOAuth2Implementation],
        hass.data.setdefault(DATA_IMPLEMENTATIONS, {}).get(domain, {}),
    )

    if DATA_PROVIDERS not in hass.data:
        return registered

    registered = dict(registered)

    for provider_domain, get_impl in hass.data[DATA_PROVIDERS].items():
        implementation = await get_impl(hass, domain)
        if implementation is not None:
            registered[provider_domain] = implementation

    return registered


async def async_get_config_entry_implementation(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> AbstractOAuth2Implementation:
    """Return the implementation for this config entry."""
    implementations = await async_get_implementations(hass, config_entry.domain)
    implementation = implementations.get(config_entry.data["auth_implementation"])

    if implementation is None:
        raise ValueError("Implementation not available")

    return implementation


@callback
def async_add_implementation_provider(
    hass: HomeAssistant,
    provider_domain: str,
    async_provide_implementation: Callable[
        [HomeAssistant, str], Awaitable[Optional[AbstractOAuth2Implementation]]
    ],
) -> None:
    """Add an implementation provider.

    If no implementation found, return None.
    """
    hass.data.setdefault(DATA_PROVIDERS, {})[
        provider_domain
    ] = async_provide_implementation


class OAuth2AuthorizeCallbackView(HomeAssistantView):
    """OAuth2 Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = "auth:external:callback"

    async def get(self, request: web.Request) -> web.Response:
        """Receive authorization code."""
        if "code" not in request.query or "state" not in request.query:
            return web.Response(
                text=f"Missing code or state parameter in {request.url}"
            )

        hass = request.app["hass"]

        state = _decode_jwt(hass, request.query["state"])

        if state is None:
            return web.Response(text="Invalid state")

        await hass.config_entries.flow.async_configure(
            flow_id=state["flow_id"], user_input=request.query["code"]
        )

        return web.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>",
        )


class OAuth2Session:
    """Session to make requests authenticated with OAuth2."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: AbstractOAuth2Implementation,
    ):
        """Initialize an OAuth2 session."""
        self.hass = hass
        self.config_entry = config_entry
        self.implementation = implementation

    @property
    def token(self) -> dict:
        """Return the token."""
        return cast(dict, self.config_entry.data["token"])

    @property
    def valid_token(self) -> bool:
        """Return if token is still valid."""
        return cast(float, self.token["expires_at"]) > time.time()

    async def async_ensure_token_valid(self) -> None:
        """Ensure that the current token is valid."""
        if self.valid_token:
            return

        new_token = await self.implementation.async_refresh_token(self.token)

        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, "token": new_token}
        )

    async def async_request(
        self, method: str, url: str, **kwargs: Any
    ) -> client.ClientResponse:
        """Make a request."""
        await self.async_ensure_token_valid()
        return await async_oauth2_request(
            self.hass, self.config_entry.data["token"], method, url, **kwargs
        )


async def async_oauth2_request(
    hass: HomeAssistant, token: dict, method: str, url: str, **kwargs: Any
) -> client.ClientResponse:
    """Make an OAuth2 authenticated request.

    This method will not refresh tokens. Use OAuth2 session for that.
    """
    session = async_get_clientsession(hass)

    return await session.request(
        method,
        url,
        **kwargs,
        headers={
            **(kwargs.get("headers") or {}),
            "authorization": f"Bearer {token['access_token']}",
        },
    )


@callback
def _encode_jwt(hass: HomeAssistant, data: dict) -> str:
    """JWT encode data."""
    secret = hass.data.get(DATA_JWT_SECRET)

    if secret is None:
        secret = hass.data[DATA_JWT_SECRET] = secrets.token_hex()

    return jwt.encode(data, secret, algorithm="HS256").decode()


@callback
def _decode_jwt(hass: HomeAssistant, encoded: str) -> Optional[dict]:
    """JWT encode data."""
    secret = cast(str, hass.data.get(DATA_JWT_SECRET))

    try:
        return jwt.decode(encoded, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
