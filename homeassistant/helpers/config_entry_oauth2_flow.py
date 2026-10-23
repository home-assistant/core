"""Config Flow using OAuth2.

This module exists of the following parts:
 - OAuth2 config flow which supports multiple OAuth2 implementations
 - OAuth2 implementation that works with local provided client ID/secret

"""

from abc import ABC, ABCMeta, abstractmethod
import asyncio
from asyncio import Lock
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
import logging
import secrets
import time
from typing import Any, ClassVar, Self, cast, override

from aiohttp import ClientError, client, web
from habluetooth import BluetoothServiceInfoBleak
import jwt
import probatio
from yarl import URL

from homeassistant import config_entries
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ImplementationUnavailableError,
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
    UnknownImplementationError,
)
from homeassistant.loader import async_get_application_credentials
from homeassistant.util.hass_dict import HassKey

from . import http, oauth2
from .network import NoURLAvailableError
from .oauth2 import async_oauth2_request
from .service_info.dhcp import DhcpServiceInfo
from .service_info.ssdp import SsdpServiceInfo
from .service_info.zeroconf import ZeroconfServiceInfo

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "AUTH_CALLBACK_PATH",
    "HEADER_FRONTEND_BASE",
    "MY_AUTH_CALLBACK_PATH",
    "AbstractAuthorizationCodeImplementation",
    "AbstractOAuth2BaseImplementation",
    "AbstractOAuth2DeviceFlowHandler",
    "AbstractOAuth2FlowHandler",
    "AbstractOAuth2Implementation",
    "DeviceAuthorization",
    "DeviceFlowError",
    "DeviceFlowImplementation",
    "DeviceFlowTimeout",
    "DeviceFlowUnauthorized",
    # Re-exported since integrations imported it from here before it moved
    # to homeassistant.exceptions.
    "ImplementationUnavailableError",
    "LocalOAuth2Implementation",
    "LocalOAuth2ImplementationWithPkce",
    "OAuth2AuthorizeCallbackView",
    "OAuth2Session",
    "async_add_implementation_provider",
    "async_get_config_entry_implementation",
    "async_get_implementations",
    "async_get_redirect_uri",
    "async_oauth2_request",
    "async_register_implementation",
]

DATA_JWT_SECRET = "oauth2_jwt_secret"
DATA_IMPLEMENTATIONS: HassKey[
    dict[str, dict[str, AbstractOAuth2BaseImplementation]]
] = HassKey("oauth2_impl")
DATA_PROVIDERS: HassKey[
    dict[
        str,
        Callable[
            [HomeAssistant, str], Awaitable[Sequence[AbstractOAuth2BaseImplementation]]
        ],
    ]
] = HassKey("oauth2_providers")
AUTH_CALLBACK_PATH = "/auth/external/callback"
HEADER_FRONTEND_BASE = "HA-Frontend-Base"
MY_AUTH_CALLBACK_PATH = "https://my.home-assistant.io/redirect/oauth"


CLOCK_OUT_OF_SYNC_MAX_SEC = 20

OAUTH_AUTHORIZE_URL_TIMEOUT_SEC = 30
OAUTH_TOKEN_TIMEOUT_SEC = 30

DEVICE_FLOW_DEFAULT_EXPIRES_IN = 10 * 365 * 24 * 60 * 60

# Abort reasons shared by all OAuth2 config flows. They are translated by the
# homeassistant integration so each flow does not repeat them in its strings.json.
_SHARED_ABORT_REASONS = frozenset(
    {
        "authorize_url_timeout",
        "missing_credentials",
        "no_url_available",
        "oauth_error",
        "oauth_failed",
        "oauth_implementation_unavailable",
        "oauth_timeout",
        "oauth_unauthorized",
        "user_rejected_authorize",
    }
)


@callback
def async_get_redirect_uri(hass: HomeAssistant) -> str:
    """Return the redirect uri."""
    if "my" in hass.config.components:
        return MY_AUTH_CALLBACK_PATH

    if (req := http.current_request.get()) is None:
        raise RuntimeError("No current request in context")

    if (ha_host := req.headers.get(HEADER_FRONTEND_BASE)) is None:
        raise RuntimeError("No header in request")

    return f"{ha_host}{AUTH_CALLBACK_PATH}"


class AbstractOAuth2BaseImplementation(ABC):
    """Base class for an OAuth2 implementation of any grant type."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the implementation."""

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain that is providing the implementation."""

    @property
    def service_domain(self) -> str:
        """Domain of the service the tokens are for.

        Defaults to the implementation itself, but an implementation that obtains
        tokens on behalf of other integrations has to name the one it serves.
        """
        return self.domain

    async def async_refresh_token(self, token: dict) -> dict:
        """Refresh a token and update expires info."""
        try:
            new_token = await self._async_refresh_token(token)
        except OAuth2TokenRequestError, OAuth2TokenRequestConnectionError:
            raise
        except ClientError as err:
            # Implementations that issue their own token request may not map their
            # failures, so callers would see a raw aiohttp error instead.
            oauth2.raise_mapped_token_error(err, self.service_domain)
        # Force int for non-compliant oauth2 providers
        try:
            new_token["expires_in"] = int(new_token["expires_in"])
        except (KeyError, TypeError, ValueError) as err:
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain) from err
        new_token["expires_at"] = time.time() + new_token["expires_in"]
        return new_token

    @abstractmethod
    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh a token."""


class AbstractAuthorizationCodeImplementation(AbstractOAuth2BaseImplementation):
    """Base class for an OAuth2 authorization code grant implementation."""

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
            flow_id=flow_id, user_input={'code': 'abcd', 'state': … }

        )

        """

    @abstractmethod
    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve external data to tokens."""


AbstractOAuth2Implementation = AbstractAuthorizationCodeImplementation


class OAuth2TokenEndpointMixin(AbstractOAuth2BaseImplementation):
    """Requests to an OAuth2 token endpoint, shared by the local implementations."""

    hass: HomeAssistant
    client_id: str
    token_url: str
    _request_headers: ClassVar[Mapping[str, str] | None] = None

    async def _token_request(self, data: dict) -> dict:
        """Make a token request.

        Raises OAuth2TokenRequestError on token request failure.
        """
        return await self._oauth2_post_request(data, self.token_url)

    async def _oauth2_post_request(
        self, data: dict, url: str, *, return_error_body: bool = False
    ) -> dict:
        """POST an OAuth2 request and convert failures to OAuth2TokenRequestError."""
        data["client_id"] = self.client_id
        return await oauth2.async_token_request(
            self.hass,
            url,
            data,
            domain=self.service_domain,
            headers=self._request_headers,
            return_error_body=return_error_body,
        )

    @override
    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh a token."""

        new_token = await self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token["refresh_token"],
            }
        )

        # Merging a response without one would keep the stale access token while
        # extending its expiry, so the session would never recover.
        if not new_token.get("access_token"):
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain)

        return {**token, **new_token}


class LocalOAuth2Implementation(
    OAuth2TokenEndpointMixin, AbstractAuthorizationCodeImplementation
):
    """Local OAuth2 implementation."""

    token_auth_method: oauth2.ClientAuthMethod = "client_secret_post"

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        token_url: str,
    ) -> None:
        """Initialize local auth implementation."""
        self.hass = hass
        self._domain = domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.token_url = token_url

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return "Local application credentials"

    @property
    @override
    def domain(self) -> str:
        """Domain providing the implementation."""
        return self._domain

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return async_get_redirect_uri(self.hass)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {}

    @property
    def extra_token_resolve_data(self) -> dict:
        """Extra data for the token resolve request."""
        return {}

    @override
    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize."""
        redirect_uri = self.redirect_uri
        return oauth2.build_authorize_url(
            self.authorize_url,
            client_id=self.client_id,
            redirect_uri=redirect_uri,
            state=_encode_jwt(
                self.hass, {"flow_id": flow_id, "redirect_uri": redirect_uri}
            ),
            extra=self.extra_authorize_data,
        )

    @override
    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        request_data: dict = {
            "grant_type": "authorization_code",
            "code": external_data["code"],
            "redirect_uri": external_data["state"]["redirect_uri"],
        }
        request_data.update(self.extra_token_resolve_data)
        return await self._token_request(request_data)

    @override
    async def _token_request(self, data: dict) -> dict:
        """Make a token request.

        Raises OAuth2TokenRequestError on token request failure.
        """
        body, headers = oauth2.client_auth(
            data, self.client_id, self.client_secret, self.token_auth_method
        )
        return await oauth2.async_token_request(
            self.hass,
            self.token_url,
            body,
            domain=self.service_domain,
            headers=headers,
        )


class LocalOAuth2ImplementationWithPkce(LocalOAuth2Implementation):
    """Local OAuth2 implementation with PKCE."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        authorize_url: str,
        token_url: str,
        client_secret: str = "",
        code_verifier_length: int = 128,
    ) -> None:
        """Initialize local auth implementation."""
        super().__init__(
            hass,
            domain,
            client_id,
            client_secret,
            authorize_url,
            token_url,
        )

        # Generate code verifier
        self.code_verifier = LocalOAuth2ImplementationWithPkce.generate_code_verifier(
            code_verifier_length
        )

    @property
    @override
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url.

        If you want to override this method,
        calling super is mandatory (for adding scopes):
        ```
        @def extra_authorize_data(self) -> dict:
            data: dict = {
                "scope": "openid profile email",
            }
            data.update(super().extra_authorize_data)
            return data
        ```
        """
        return {
            "code_challenge": LocalOAuth2ImplementationWithPkce.compute_code_challenge(
                self.code_verifier
            ),
            "code_challenge_method": "S256",
        }

    @property
    @override
    def extra_token_resolve_data(self) -> dict:
        """Extra data that needs to be included in the token resolve request.

        If you want to override this method,
        calling super is mandatory (for adding `someKey`):
        ```
        @def extra_token_resolve_data(self) -> dict:
            data: dict = {
                "someKey": "someValue",
            }
            data.update(super().extra_token_resolve_data)
            return data
        ```
        """

        return {"code_verifier": self.code_verifier}

    @staticmethod
    def generate_code_verifier(code_verifier_length: int = 128) -> str:
        """Generate a code verifier."""
        return oauth2.generate_code_verifier(code_verifier_length)

    @staticmethod
    def compute_code_challenge(code_verifier: str) -> str:
        """Compute the code challenge."""
        return oauth2.compute_code_challenge(code_verifier)


@dataclass(frozen=True, kw_only=True)
class DeviceAuthorization:
    """Device authorization response (RFC 8628 section 3.2).

    device_code: sent back to the token endpoint on every poll.
    user_code, verification_uri: shown to the user, who enters the code there.
    verification_uri_complete: optional, verification_uri with the code included.
    expires_in: lifetime of the device_code in seconds, so the polling deadline.
    interval: optional minimum seconds between polls, default 5.
    """

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str | None
    expires_in: int
    interval: int

    @classmethod
    def from_response(cls, response: Mapping[str, Any]) -> Self:
        """Parse a device authorization response.

        Accepts the verification_url name some providers use and numbers sent as
        strings. Raises DeviceFlowError when the response is unusable.
        """
        try:
            return cls(
                device_code=response["device_code"],
                user_code=response["user_code"],
                verification_uri=response.get("verification_uri")
                or response["verification_url"],
                verification_uri_complete=response.get("verification_uri_complete"),
                expires_in=int(response["expires_in"]),
                # At least the RFC 8628 default, so a zero or negative interval
                # can't make the poll loop hammer the token endpoint
                interval=max(int(response.get("interval", 5)), 5),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise DeviceFlowError("Invalid device authorization response") from err


class DeviceFlowImplementation(OAuth2TokenEndpointMixin):
    """Device authorization grant implementation (RFC 8628).

    The device flow config flow handler uses it as follows:
    1. async_register_device requests a device code and returns the validated
       DeviceAuthorization (section 3.2).
    2. The handler shows its user_code and verification_uri to the user.
    3. async_check_device_activation polls the token endpoint (section 3.4) until
       the user approved (section 3.5), the code expired, or the server refused.

    The client is public: requests carry the client_id and never a secret.
    Tokens without expires_in get DEVICE_FLOW_DEFAULT_EXPIRES_IN, so providers
    that issue non-expiring tokens work with OAuth2Session.
    """

    _request_headers = {"Accept": "application/json"}

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        authorize_url: str,
        token_url: str,
    ) -> None:
        """Initialize device flow implementation."""
        self.hass = hass
        self._domain = domain
        self.client_id = client_id
        self.authorize_url = authorize_url
        self.token_url = token_url

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return "Device authorization"

    @property
    @override
    def domain(self) -> str:
        """Domain providing the implementation."""
        return self._domain

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data for the device authorization request, such as the scope."""
        return {}

    async def async_register_device(
        self, extra_data: Mapping[str, Any] | None = None
    ) -> DeviceAuthorization:
        """Request a device code and return the device authorization.

        Posts client_id plus extra_authorize_data and extra_data (such as scope)
        to the device authorization endpoint (RFC 8628 section 3.1).
        """
        response = await self._oauth2_post_request(
            {
                key: str(value)
                for key, value in {
                    **self.extra_authorize_data,
                    **(extra_data or {}),
                }.items()
                if value is not None
            },
            self.authorize_url,
        )
        return DeviceAuthorization.from_response(response)

    async def async_check_device_activation(
        self, device: DeviceAuthorization
    ) -> dict[str, Any]:
        """Poll the token endpoint until the user authorized the device.

        Each poll posts grant_type device_code, the device_code and
        client_id (RFC 8628 section 3.4). Error codes (section 3.5):
        authorization_pending keeps polling, slow_down adds 5 seconds (or takes
        the server's interval, at most 120 seconds), access_denied raises
        DeviceFlowUnauthorized, expired_token raises DeviceFlowTimeout and any
        other raises DeviceFlowError. Connection timeouts, 429 and 5xx double the interval.
        """
        deadline = time.monotonic() + device.expires_in
        interval = device.interval
        while True:
            await asyncio.sleep(interval)
            if time.monotonic() >= deadline:
                raise DeviceFlowTimeout
            try:
                async with asyncio.timeout(OAUTH_TOKEN_TIMEOUT_SEC):
                    response = await self._oauth2_post_request(
                        {
                            "grant_type": (
                                "urn:ietf:params:oauth:grant-type:device_code"
                            ),
                            "device_code": device.device_code,
                        },
                        self.token_url,
                        return_error_body=True,
                    )
            except (
                TimeoutError,
                OAuth2TokenRequestConnectionError,
                OAuth2TokenRequestTransientError,
            ):
                # RFC 8628 section 3.5: back off on connection timeouts
                interval = max(interval, min(interval * 2, 60))
                _LOGGER.debug("Device token request failed, retrying in %s s", interval)
                continue
            except (OAuth2TokenRequestError, ValueError) as err:
                raise DeviceFlowError("Device token request failed") from err

            match response.get("error"):
                case None:
                    if not response.get("access_token"):
                        raise DeviceFlowError("Token response without access_token")
                    return self._with_default_expiry(response)
                case "authorization_pending":
                    pass
                case "slow_down":
                    interval += 5
                    with suppress(KeyError, TypeError, ValueError):
                        interval = max(interval, int(response["interval"]))
                    interval = min(interval, 120)
                    _LOGGER.debug("Asked to slow down, polling every %s s", interval)
                case "access_denied":
                    raise DeviceFlowUnauthorized
                case "expired_token":
                    raise DeviceFlowTimeout
                case error:
                    raise DeviceFlowError(f"Device token request failed: {error}")

    @override
    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh a token."""
        if "refresh_token" not in token:
            # Non-expiring tokens come without one, so only reauth can renew them
            raise ConfigEntryAuthFailed(
                translation_domain=HOMEASSISTANT_DOMAIN,
                translation_key="oauth2_helper_reauth_required",
                translation_placeholders={"domain": self.service_domain},
            )
        return self._with_default_expiry(await super()._async_refresh_token(token))

    @staticmethod
    def _with_default_expiry(token: dict[str, Any]) -> dict[str, Any]:
        """Treat a token without expires_in as non-expiring."""
        if token.get("expires_in") is None:
            token["expires_in"] = DEVICE_FLOW_DEFAULT_EXPIRES_IN
        return token


class AbstractOAuth2BaseFlowHandler(config_entries.ConfigFlow, metaclass=ABCMeta):
    """Handle a config flow for any OAuth2 grant type."""

    DOMAIN = ""

    VERSION = 1

    def __init__(self) -> None:
        """Instantiate config flow."""
        if self.DOMAIN == "":
            raise TypeError(
                f"Can't instantiate class {self.__class__.__name__} without DOMAIN"
                " being set"
            )

        self.flow_impl: AbstractOAuth2BaseImplementation = None  # type: ignore[assignment]

    @callback
    @override
    def async_abort(
        self,
        *,
        reason: str,
        description_placeholders: Mapping[str, str] | None = None,
        translation_domain: str | None = None,
        next_flow: tuple[config_entries.FlowType, str] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Abort the flow, translating shared OAuth2 reasons centrally."""
        if translation_domain is None and reason in _SHARED_ABORT_REASONS:
            translation_domain = HOMEASSISTANT_DOMAIN
        return super().async_abort(
            reason=reason,
            description_placeholders=description_placeholders,
            translation_domain=translation_domain,
            next_flow=next_flow,
        )

    @property
    @abstractmethod
    def logger(self) -> logging.Logger:
        """Return logger."""

    async def async_step_pick_implementation(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow start."""
        try:
            implementations = await async_get_implementations(self.hass, self.DOMAIN)
        except ImplementationUnavailableError as err:
            self.logger.error(
                "No OAuth2 implementations available: %s",
                ", ".join(str(e) for e in err.args),
            )
            return self.async_abort(reason="oauth_implementation_unavailable")

        if user_input is not None:
            # Reauth and reconfigure steps pass the stored implementation, which is
            # gone when its credentials were removed. Fall through to let the user
            # pick or create credentials instead of failing the flow.
            if (
                implementation := implementations.get(user_input["implementation"])
            ) is not None:
                self.flow_impl = implementation
                return await self.async_step_auth()

        if not implementations:
            if self.DOMAIN in await async_get_application_credentials(self.hass):
                return self.async_abort(reason="missing_credentials")
            return self.async_abort(reason="missing_configuration")

        req = http.current_request.get()
        if len(implementations) == 1 and req is not None:
            # Pick first implementation if we have only one, but only
            # if this is triggered by a user interaction (request).
            self.flow_impl = list(implementations.values())[0]
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="pick_implementation",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        "implementation", default=list(implementations)[0]
                    ): probatio.In(
                        {key: impl.name for key, impl in implementations.items()}
                    )
                }
            ),
        )

    @abstractmethod
    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Obtain the tokens with the picked implementation."""

    async def _async_create_entry_from_token(
        self, token: dict
    ) -> config_entries.ConfigFlowResult:
        """Normalise the token expiry and create the entry."""
        if "expires_in" not in token:
            _LOGGER.warning("Invalid token: %s", token)
            return self.async_abort(reason="oauth_error")

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

    async def async_oauth_create_entry(
        self, data: dict
    ) -> config_entries.ConfigFlowResult:
        """Create an entry for the flow.

        Ok to override if you want to fetch extra info or even add another step.
        """
        return self.async_create_entry(title=self.flow_impl.name, data=data)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow start."""
        return await self.async_step_pick_implementation(user_input)

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        return await self.async_step_oauth_discovery()

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by DHCP discovery."""
        return await self.async_step_oauth_discovery()

    @override
    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by Homekit discovery."""
        return await self.async_step_oauth_discovery()

    @override
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by SSDP discovery."""
        return await self.async_step_oauth_discovery()

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by Zeroconf discovery."""
        return await self.async_step_oauth_discovery()

    async def async_step_oauth_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by a discovery method."""
        if user_input is not None:
            return await self.async_step_user()
        await self._async_handle_discovery_without_unique_id()
        return self.async_show_form(step_id="oauth_discovery")


class AbstractOAuth2FlowHandler(AbstractOAuth2BaseFlowHandler, metaclass=ABCMeta):
    """Handle an authorization code grant config flow."""

    flow_impl: AbstractOAuth2Implementation

    def __init__(self) -> None:
        """Instantiate config flow."""
        super().__init__()
        self.external_data: Any = None

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {}

    async def async_generate_authorize_url(self) -> str:
        """Generate a url for the user to authorize."""
        url = await self.flow_impl.async_generate_authorize_url(self.flow_id)
        return str(URL(url).update_query(self.extra_authorize_data))

    @override
    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create an entry for auth."""
        # Flow has been triggered by external data
        if user_input is not None:
            self.external_data = user_input
            next_step = "authorize_rejected" if "error" in user_input else "creation"
            return self.async_external_step_done(next_step_id=next_step)

        try:
            async with asyncio.timeout(OAUTH_AUTHORIZE_URL_TIMEOUT_SEC):
                url = await self.async_generate_authorize_url()
        except TimeoutError as err:
            _LOGGER.error("Timeout generating authorize url: %s", err)
            return self.async_abort(reason="authorize_url_timeout")
        except NoURLAvailableError:
            return self.async_abort(
                reason="no_url_available",
                description_placeholders={
                    "docs_url": (
                        "https://www.home-assistant.io/more-info/no-url-available"
                    )
                },
            )

        return self.async_external_step(step_id="auth", url=url)

    async def async_step_creation(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create config entry from external data."""
        _LOGGER.debug("Creating config entry from external data")

        try:
            async with asyncio.timeout(OAUTH_TOKEN_TIMEOUT_SEC):
                token = await self.flow_impl.async_resolve_external_data(
                    self.external_data
                )
        except TimeoutError as err:
            _LOGGER.error("Timeout resolving OAuth token: %s", err)
            return self.async_abort(reason="oauth_timeout")
        except (
            OAuth2TokenRequestError,
            ClientError,
        ) as err:
            _LOGGER.error("Error resolving OAuth token: %s", err)
            if isinstance(err, OAuth2TokenRequestReauthError):
                return self.async_abort(reason="oauth_unauthorized")
            return self.async_abort(reason="oauth_failed")

        return await self._async_create_entry_from_token(token)

    async def async_step_authorize_rejected(
        self, data: None = None
    ) -> config_entries.ConfigFlowResult:
        """Step to handle flow rejection."""
        return self.async_abort(
            reason="user_rejected_authorize",
            description_placeholders={"error": self.external_data["error"]},
        )

    @classmethod
    def async_register_implementation(
        cls, hass: HomeAssistant, local_impl: LocalOAuth2Implementation
    ) -> None:
        """Register a local implementation."""
        async_register_implementation(hass, cls.DOMAIN, local_impl)


class AbstractOAuth2DeviceFlowHandler(AbstractOAuth2BaseFlowHandler, metaclass=ABCMeta):
    """Handle a device authorization grant config flow (RFC 8628).

    Integrations ship the wait_for_device progress string, with the url,
    url_complete and code placeholders, in their strings.json.
    """

    flow_impl: DeviceFlowImplementation
    device_authorization: DeviceAuthorization

    def __init__(self) -> None:
        """Instantiate device flow handler."""
        super().__init__()
        self.login_task: asyncio.Task[dict[str, Any]] | None = None
        self.device_token: dict[str, Any] = {}
        self.device_flow_error: BaseException | None = None

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data for the device authorization request, such as the scope."""
        return {}

    @override
    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Run the auth step for device flow."""
        return await self.async_step_device_flow()

    async def async_step_device_flow(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the user code and wait for the user to authorize the device."""
        if self.login_task and self.login_task.done():
            if exc := self.login_task.exception():
                self.device_flow_error = exc
                return self.async_show_progress_done(next_step_id="device_flow_error")
            self.device_token = self.login_task.result()
            return self.async_show_progress_done(next_step_id="device_flow_complete")

        if self.login_task is None:
            try:
                async with asyncio.timeout(OAUTH_AUTHORIZE_URL_TIMEOUT_SEC):
                    self.device_authorization = (
                        await self.flow_impl.async_register_device(
                            self.extra_authorize_data
                        )
                    )
            except TimeoutError as err:
                _LOGGER.error("Timeout registering device: %s", err)
                return self.async_abort(reason="authorize_url_timeout")
            except OAuth2TokenRequestReauthError as err:
                _LOGGER.error("Error registering device: %s", err)
                return self.async_abort(reason="oauth_unauthorized")
            except ClientError as err:
                _LOGGER.error("Error registering device: %s", err)
                return self.async_abort(reason="oauth_failed")
            except (DeviceFlowError, ValueError) as err:
                _LOGGER.error("Invalid device authorization response: %s", err)
                return self.async_abort(reason="oauth_error")

            self.login_task = self.hass.async_create_task(
                self.flow_impl.async_check_device_activation(self.device_authorization)
            )

        return self.async_show_progress(
            step_id="device_flow",
            progress_action="wait_for_device",
            description_placeholders={
                "url": self.device_authorization.verification_uri,
                # Includes the code, for a link the user only has to open
                "url_complete": (
                    self.device_authorization.verification_uri_complete
                    or self.device_authorization.verification_uri
                ),
                "code": self.device_authorization.user_code,
            },
            progress_task=self.login_task,
        )

    async def async_step_device_flow_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create the entry once the user authorized the device."""
        return await self._async_create_entry_from_token(self.device_token)

    async def async_step_device_flow_error(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Abort the flow when waiting for the authorization failed."""
        match self.device_flow_error:
            case DeviceFlowTimeout():
                return self.async_abort(reason="oauth_timeout")
            case DeviceFlowUnauthorized():
                return self.async_abort(
                    reason="user_rejected_authorize",
                    description_placeholders={"error": "access_denied"},
                )
            case DeviceFlowError():
                _LOGGER.error("Device authorization failed: %s", self.device_flow_error)
            case _:
                _LOGGER.error(
                    "Unexpected error during device authorization",
                    exc_info=self.device_flow_error,
                )
        return self.async_abort(reason="oauth_error")


@callback
def async_register_implementation(
    hass: HomeAssistant, domain: str, implementation: AbstractOAuth2BaseImplementation
) -> None:
    """Register an OAuth2 flow implementation for an integration."""
    implementations = hass.data.setdefault(DATA_IMPLEMENTATIONS, {})
    implementations.setdefault(domain, {})[implementation.domain] = implementation


async def _async_get_implementations(
    hass: HomeAssistant, domain: str
) -> tuple[
    dict[str, AbstractOAuth2BaseImplementation], list[ImplementationUnavailableError]
]:
    """Return OAuth2 implementations for specified domain and any provider failures."""
    registered = dict(hass.data.setdefault(DATA_IMPLEMENTATIONS, {}).get(domain, {}))
    exceptions: list[ImplementationUnavailableError] = []

    for get_impl in list(hass.data.get(DATA_PROVIDERS, {}).values()):
        try:
            for impl in await get_impl(hass, domain):
                registered[impl.domain] = impl
        except ImplementationUnavailableError as err:
            exceptions.append(err)

    return registered, exceptions


async def async_get_implementations(
    hass: HomeAssistant, domain: str
) -> dict[str, AbstractOAuth2BaseImplementation]:
    """Return OAuth2 implementations for specified domain."""
    registered, exceptions = await _async_get_implementations(hass, domain)

    if not registered and exceptions:
        raise ImplementationUnavailableError(*exceptions)

    return registered


async def async_get_config_entry_implementation(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> AbstractOAuth2Implementation:
    """Return the implementation for this config entry."""
    implementations, exceptions = await _async_get_implementations(
        hass, config_entry.domain
    )
    implementation = implementations.get(config_entry.data["auth_implementation"])

    if implementation is not None:
        # Callers rely on the authorization code type; device flow entries get a
        # DeviceFlowImplementation, which OAuth2Session accepts as well.
        return cast(AbstractOAuth2Implementation, implementation)

    if exceptions:
        # A provider is down, so the configured implementation may still come back.
        # Retry instead of asking the user to link the account again.
        raise ImplementationUnavailableError(*exceptions)

    raise UnknownImplementationError


@callback
def async_add_implementation_provider(
    hass: HomeAssistant,
    provider_domain: str,
    async_provide_implementation: Callable[
        [HomeAssistant, str], Awaitable[Sequence[AbstractOAuth2BaseImplementation]]
    ],
) -> None:
    """Add an implementation provider.

    If no implementation found, return None.
    """
    hass.data.setdefault(DATA_PROVIDERS, {})[provider_domain] = (
        async_provide_implementation
    )


class OAuth2AuthorizeCallbackView(http.HomeAssistantView):
    """OAuth2 Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = "auth:external:callback"

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

        user_input: dict[str, Any] = {"state": state}

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


class OAuth2Session:
    """Session to make requests authenticated with OAuth2."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: AbstractOAuth2BaseImplementation,
    ) -> None:
        """Initialize an OAuth2 session."""
        self.hass = hass
        self.config_entry = config_entry
        self.implementation = implementation
        self._token_lock = Lock()

    @property
    def token(self) -> dict:
        """Return the token."""
        return cast(dict, self.config_entry.data["token"])

    @property
    def valid_token(self) -> bool:
        """Return if token is still valid."""
        return (
            cast(float, self.token["expires_at"])
            > time.time() + CLOCK_OUT_OF_SYNC_MAX_SEC
        )

    async def async_ensure_token_valid(self) -> None:
        """Ensure that the current token is valid."""
        async with self._token_lock:
            if self.valid_token:
                return

            try:
                new_token = await self.implementation.async_refresh_token(self.token)
            except OAuth2TokenRequestReauthError:
                # Start reauth here so it also happens for callers that map the
                # error onto a recoverable one, which would retry indefinitely.
                self.config_entry.async_start_reauth_if_available(self.hass)
                raise

            # Checked before storing, so reads can trust what is on the entry.
            if any(
                new_token.get(field) in (None, "")
                for field in ("access_token", "expires_at")
            ):
                raise OAuth2TokenRequestConnectionError(
                    domain=self.implementation.service_domain
                )

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


@callback
def _encode_jwt(hass: HomeAssistant, data: dict) -> str:
    """JWT encode data."""
    if (secret := hass.data.get(DATA_JWT_SECRET)) is None:
        secret = hass.data[DATA_JWT_SECRET] = secrets.token_hex()

    return jwt.encode(data, secret, algorithm="HS256")


@callback
def _decode_jwt(hass: HomeAssistant, encoded: str) -> dict[str, Any] | None:
    """JWT encode data."""
    secret: str | None = hass.data.get(DATA_JWT_SECRET)

    if secret is None:
        return None

    try:
        return jwt.decode(encoded, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


class DeviceFlowError(HomeAssistantError):
    """Exception raised for device flow errors."""


class DeviceFlowTimeout(DeviceFlowError):
    """Exception raised when device flow times out."""


class DeviceFlowUnauthorized(DeviceFlowError):
    """Exception raised when user denies authorization in device flow."""
