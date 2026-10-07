"""Config flow for the Model Context Protocol integration."""

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import logging
from typing import Any, cast, override

import httpx  # noqa: TID251
import httpx2
import probatio
from yarl import URL

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    AuthorizationServer,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_DOMAIN,
    CONF_ID,
    CONF_TOKEN,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, UnknownImplementationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    async_get_implementations,
    async_get_redirect_uri,
)
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from . import async_get_config_entry_implementation
from .application_credentials import authorization_server_context
from .auth import AuthenticateHeader
from .const import (
    CONF_AUTHORIZATION_URL,
    CONF_SCOPE,
    CONF_SLUG,
    CONF_TOKEN_URL,
    DCR_CLIENT_NAME,
    DOMAIN,
)
from .coordinator import TokenManager, mcp_client
from .registration import (
    ClientRegistrationError,
    RegisteredClientIdentity,
    async_register_dynamic_client,
    decode_registered_client_id,
    encode_registered_client_id,
    registered_client_auth_domain,
    resolve_registration_endpoint,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): str,
    }
)

OAUTH_PROTECTED_RESOURCE_ENDPOINT = "/.well-known/oauth-protected-resource"


@dataclass
class ResourceMetadata:
    """Class to hold protected resource metadata defined in rfc9728."""

    authorization_servers: list[str]
    """List of authorization server URLs."""

    supported_scopes: list[str] | None = None
    """List of supported scopes."""


# OAuth server discovery endpoint for rfc8414
OAUTH_DISCOVERY_ENDPOINT = ".well-known/oauth-authorization-server"
MCP_DISCOVERY_HEADERS = {
    "MCP-Protocol-Version": "2025-03-26",
}

EXAMPLE_URL = "http://example/mcp"


@dataclass
class OAuthConfig:
    """Class to hold OAuth configuration."""

    authorization_server: AuthorizationServer
    scopes: list[str] | None = None
    registration_endpoint: str | None = None
    token_endpoint_auth_methods: list[str] | None = None


async def async_discover_authorization_server(
    hass: HomeAssistant, auth_server_url: str
) -> OAuthConfig:
    """Perform OAuth 2.0 Authorization Server Metadata discovery as per RFC8414."""
    parsed_url = URL(auth_server_url)
    urls_to_try = [
        str(parsed_url.with_path(path))
        for path in _authorization_server_discovery_paths(parsed_url)
    ]
    # Pick any successful response and propagate exceptions except for
    # 404 where we fall back to assuming some default paths.
    try:
        response = await _async_fetch_any(hass, urls_to_try)
    except NotFoundError:
        _LOGGER.info("Authorization Server Metadata not found, using default paths")
        return OAuthConfig(
            authorization_server=AuthorizationServer(
                authorize_url=str(parsed_url.with_path("/authorize")),
                token_url=str(parsed_url.with_path("/token")),
            )
        )

    data = response.json()
    authorize_url = data["authorization_endpoint"]
    token_url = data["token_endpoint"]
    if authorize_url.startswith("/"):
        authorize_url = str(parsed_url.with_path(authorize_url))
    if token_url.startswith("/"):
        token_url = str(parsed_url.with_path(token_url))
    # We have no way to know the minimum set of scopes needed, so request
    # all of them and let the user limit during the authorization step.
    scopes = data.get("scopes_supported")
    registration_endpoint = data.get("registration_endpoint")
    if not isinstance(registration_endpoint, str) or not registration_endpoint:
        registration_endpoint = None
    else:
        registration_endpoint = resolve_registration_endpoint(
            auth_server_url, registration_endpoint
        )
    return OAuthConfig(
        authorization_server=AuthorizationServer(
            authorize_url=authorize_url,
            token_url=token_url,
        ),
        scopes=scopes,
        registration_endpoint=registration_endpoint,
        token_endpoint_auth_methods=_string_list(
            data, "token_endpoint_auth_methods_supported"
        ),
    )


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], token_manager: TokenManager | None = None
) -> dict[str, Any]:
    """Validate the user input and connect to the MCP server."""
    url = data[CONF_URL]
    try:
        cv.url(url)  # Cannot be added to schema directly
    except probatio.Invalid as error:
        raise InvalidUrl from error
    try:
        async with mcp_client(hass, url, token_manager=token_manager) as (
            _session,
            response,
        ):
            if not response.capabilities.tools:
                raise MissingCapabilities(
                    f"MCP Server {url} does not support 'Tools' capability"
                )
            return {"title": response.serverInfo.name}
    except (httpx.TimeoutException, httpx2.TimeoutException) as error:
        _LOGGER.info("Timeout connecting to MCP server: %s", error)
        raise TimeoutConnectError from error
    except (httpx.HTTPStatusError, httpx2.HTTPStatusError) as error:
        # The MCP SDK raises httpx.HTTPStatusError. Home Assistant's HTTP
        # client raises httpx2.HTTPStatusError. The classes are not related.
        _LOGGER.info("Cannot connect to MCP server: %s", error)
        if error.response.status_code == 401:
            auth_header = AuthenticateHeader.from_header(url, error.response)
            raise InvalidAuth(auth_header) from error
        raise CannotConnect from error
    except (httpx.HTTPError, httpx2.HTTPError) as error:
        _LOGGER.info("Cannot connect to MCP server: %s", error)
        raise CannotConnect from error


class ModelContextProtocolConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Model Context Protocol."""

    VERSION = 1
    DOMAIN = DOMAIN
    logger = _LOGGER

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.data: dict[str, Any] = {}
        self.oauth_config: OAuthConfig | None = None
        self.auth_header: AuthenticateHeader | None = None
        self.addon_name: str = ""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Match an existing URL before OAuth. The unauthenticated success
            # path is not the only way a duplicate can be created.
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidUrl:
                errors[CONF_URL] = "invalid_url"
            except TimeoutConnectError:
                errors["base"] = "timeout_connect"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth as err:
                self.auth_header = err.metadata
                self.data[CONF_URL] = user_input[CONF_URL]
                return await self.async_step_auth_discovery()
            except MissingCapabilities:
                return self.async_abort(reason="missing_capabilities")
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"example_url": EXAMPLE_URL},
        )

    @override
    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery of an MCP server provided by an app."""
        url = discovery_info.config.get(CONF_URL)
        try:
            # An unparsable URL, such as an unmatched IPv6 bracket, raises ValueError
            url = cv.url(url)
        except probatio.Invalid, ValueError:
            _LOGGER.debug(
                "Ignoring discovery from app %s with invalid URL: %s",
                discovery_info.slug,
                url,
            )
            return self.async_abort(reason="invalid_discovery_info")

        await self.async_set_unique_id(discovery_info.uuid)
        self._abort_if_unique_id_configured(updates={CONF_URL: url})
        self._async_abort_entries_match({CONF_URL: url})
        self.data[CONF_URL] = url
        self.data[CONF_SLUG] = discovery_info.slug
        self.addon_name = discovery_info.name
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the MCP server provided by an app."""
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="hassio_confirm",
                description_placeholders={"addon": self.addon_name},
            )

        try:
            info = await validate_input(self.hass, self.data)
        except TimeoutConnectError:
            return self.async_abort(reason="timeout_connect")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidAuth as err:
            self.auth_header = err.metadata
            return await self.async_step_auth_discovery()
        except MissingCapabilities:
            return self.async_abort(reason="missing_capabilities")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(title=info["title"], data=self.data)

    async def async_step_auth_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the OAuth server discovery step.

        Since this OAuth server requires authentication, this step will attempt
        to find the OAuth metadata then run the OAuth authentication flow.
        """
        resource_metadata: ResourceMetadata | None = None
        try:
            if self.auth_header:
                _LOGGER.debug(
                    "Resource metadata discovery from header: %s", self.auth_header
                )
                resource_metadata = await async_discover_protected_resource(
                    self.hass,
                    self.auth_header.resource_metadata_url,
                    self.data[CONF_URL],
                )
                _LOGGER.debug("Protected resource metadata: %s", resource_metadata)
                oauth_config = await async_discover_authorization_server(
                    self.hass,
                    # Use the first authorization server from the
                    # resource metadata as it is the most common to
                    # have only one and there is not a defined
                    # strategy.
                    resource_metadata.authorization_servers[0],
                )
            else:
                _LOGGER.debug(
                    "Discovering authorization server without"
                    " protected resource metadata"
                )
                oauth_config = await async_discover_authorization_server(
                    self.hass,
                    self.data[CONF_URL],
                )
        except TimeoutConnectError:
            return self.async_abort(reason="timeout_connect")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        else:
            _LOGGER.info("OAuth configuration: %s", oauth_config)
            self.oauth_config = oauth_config
            self.data.update(
                {
                    CONF_AUTHORIZATION_URL: (
                        oauth_config.authorization_server.authorize_url
                    ),
                    CONF_TOKEN_URL: oauth_config.authorization_server.token_url,
                    CONF_SCOPE: _select_scopes(
                        self.auth_header, oauth_config, resource_metadata
                    ),
                }
            )
            # Servers that advertise RFC 7591 registration issue a client
            # themselves, so the user does not create application credentials.
            if oauth_config.registration_endpoint:
                return await self._async_register_dynamic_client()
            return await self.async_step_credentials_choice()

    def authorization_server(self) -> AuthorizationServer:
        """Return the authorization server provided by the MCP server."""
        return AuthorizationServer(
            self.data[CONF_AUTHORIZATION_URL],
            self.data[CONF_TOKEN_URL],
        )

    @property
    @override
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        data = {
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }
        if self.data and (scopes := self.data[CONF_SCOPE]) is not None:
            data[CONF_SCOPE] = " ".join(scopes)
        data.update(super().extra_authorize_data)
        return data

    def _async_existing_registered_auth_domain(self) -> str | None:
        """Return a stored client for this authorization server, if one exists."""
        storage = self.hass.data.get(APPLICATION_CREDENTIALS_DOMAIN)
        if storage is None:
            return None
        authorize_url = self.data[CONF_AUTHORIZATION_URL]
        token_url = self.data[CONF_TOKEN_URL]
        for item in storage.async_items():
            if item[CONF_DOMAIN] != DOMAIN:
                continue
            identity = decode_registered_client_id(item[CONF_CLIENT_ID])
            if identity is None:
                continue
            if (
                identity.authorize_url == authorize_url
                and identity.token_url == token_url
            ):
                return item[CONF_ID]
        return None

    async def _async_register_dynamic_client(self) -> ConfigFlowResult:
        """Register an OAuth client and continue the authorize flow."""
        if self.oauth_config is None or not self.oauth_config.registration_endpoint:
            return self.async_abort(reason="oauth_registration_failed")
        auth_domain = self._async_existing_registered_auth_domain()
        if auth_domain is None:
            try:
                redirect_uri = async_get_redirect_uri(self.hass)
            except RuntimeError as err:
                _LOGGER.debug("OAuth redirect URI is not available: %s", err)
                return self.async_abort(
                    reason="no_url_available",
                    description_placeholders={
                        "docs_url": (
                            "https://www.home-assistant.io/more-info/no-url-available"
                        )
                    },
                    # OAuth helper would otherwise retarget this shared reason.
                    translation_domain=DOMAIN,
                )
            try:
                registered = await async_register_dynamic_client(
                    self.oauth_config.registration_endpoint,
                    redirect_uri,
                    token_endpoint_auth_methods=(
                        self.oauth_config.token_endpoint_auth_methods
                    ),
                    scopes=self.data[CONF_SCOPE],
                )
            except ClientRegistrationError:
                _LOGGER.debug("Dynamic client registration failed", exc_info=True)
                return self.async_abort(reason="oauth_registration_failed")
            except httpx.TimeoutException, httpx2.TimeoutException:
                _LOGGER.debug("Timeout during dynamic client registration")
                return self.async_abort(reason="timeout_connect")
            except httpx.HTTPError, httpx2.HTTPError:
                _LOGGER.debug("Cannot connect during dynamic client registration")
                return self.async_abort(reason="cannot_connect")

            encoded_client_id = encode_registered_client_id(
                RegisteredClientIdentity(
                    authorize_url=self.data[CONF_AUTHORIZATION_URL],
                    token_url=self.data[CONF_TOKEN_URL],
                    client_id=registered.client_id,
                    method=registered.token_endpoint_auth_method,
                )
            )
            auth_domain = registered_client_auth_domain(encoded_client_id)
            try:
                await async_import_client_credential(
                    self.hass,
                    DOMAIN,
                    ClientCredential(
                        encoded_client_id,
                        registered.client_secret,
                        DCR_CLIENT_NAME,
                    ),
                    auth_domain,
                )
            except ValueError:
                _LOGGER.debug(
                    "Could not store dynamically registered client", exc_info=True
                )
                return self.async_abort(reason="oauth_registration_failed")
        else:
            _LOGGER.debug(
                "Reusing dynamically registered client for %s",
                self.data[CONF_AUTHORIZATION_URL],
            )

        with authorization_server_context(self.authorization_server()):
            implementations = await async_get_implementations(self.hass, self.DOMAIN)
        implementation = implementations.get(auth_domain)
        if implementation is None:
            _LOGGER.debug(
                "Dynamically registered client %s is not available", auth_domain
            )
            return self.async_abort(reason="oauth_registration_failed")
        self.flow_impl = implementation
        return await self.async_step_auth()

    async def async_step_credentials_choice(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to ask they user if they would like to add credentials.

        This is needed since we can't automatically assume existing credentials
        should be used given they may be for another existing server.
        """
        with authorization_server_context(self.authorization_server()):
            if not await async_get_implementations(self.hass, self.DOMAIN):
                return await self.async_step_new_credentials()
            return self.async_show_menu(
                step_id="credentials_choice",
                menu_options=["pick_implementation", "new_credentials"],
            )

    async def async_step_new_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to take the frontend flow to enter new credentials."""
        return self.async_abort(reason="missing_credentials")

    @override
    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pick implementation step.

        This exists to dynamically set application credentials Authorization Server
        based on the values form the OAuth discovery step.
        """
        with authorization_server_context(self.authorization_server()):
            return await super().async_step_pick_implementation(user_input)

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for the flow.

        Ok to override if you want to fetch extra info or even add another step.
        """
        config_entry_data = {
            **self.data,
            **data,
        }

        async def token_manager() -> str:
            return cast(str, data[CONF_TOKEN][CONF_ACCESS_TOKEN])

        try:
            info = await validate_input(self.hass, config_entry_data, token_manager)
        except TimeoutConnectError:
            return self.async_abort(reason="timeout_connect")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except MissingCapabilities:
            return self.async_abort(reason="missing_capabilities")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=config_entry_data
            )
        # OAuth entries have no unique id. The application credential identifies
        # the client, not the MCP server, so two URLs that share a client must
        # not replace each other. A Supervisor discovery keeps its uuid.
        return self.async_create_entry(
            title=info["title"],
            data=config_entry_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        if entry_data and "auth_header" in entry_data:
            self.auth_header = entry_data["auth_header"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        config_entry = self._get_reauth_entry()
        self.data = {**config_entry.data}
        if "auth_implementation" not in self.data:
            # For entries configured without authentication (no-auth), any authentication
            # failure (from a tool call or coordinator update) requires upgrading to OAuth.
            # We bypass validate_input connection handshake (which might succeed if the server
            # doesn't restrict the connection handshake itself) and proceed directly to OAuth discovery.
            return await self.async_step_auth_discovery()

        try:
            self.flow_impl = await async_get_config_entry_implementation(  # type: ignore[assignment]
                self.hass, config_entry
            )
        except UnknownImplementationError:
            # The credentials were removed, let the user pick or create new ones
            return await self.async_step_auth_discovery()
        return await self.async_step_auth()


async def _async_fetch_any(
    hass: HomeAssistant,
    urls: Iterable[str],
) -> httpx2.Response:
    """Fetch all URLs concurrently and return the first successful response."""

    async def fetch(url: str) -> httpx2.Response:
        _LOGGER.debug("Fetching URL %s", url)
        try:
            async with httpx2.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response
        except httpx2.TimeoutException as error:
            _LOGGER.debug("Timeout fetching URL %s: %s", url, error)
            raise TimeoutConnectError from error
        except httpx2.HTTPStatusError as error:
            _LOGGER.debug("Server error for URL %s: %s", url, error)
            if error.response.status_code == 404:
                raise NotFoundError from error
            raise CannotConnect from error
        except httpx2.HTTPError as error:
            _LOGGER.debug("Cannot fetch URL %s: %s", url, error)
            raise CannotConnect from error

    tasks = [asyncio.create_task(fetch(url)) for url in urls]
    return_err: Exception | None = None
    try:
        for future in asyncio.as_completed(tasks):
            try:
                return await future
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Fetch failed: %s", err)
                if return_err is None:
                    return_err = err
                continue
    finally:
        for task in tasks:
            task.cancel()

    raise return_err or CannotConnect("No responses received from any URL")


def _protected_resource_urls(auth_url: str, mcp_server_url: str) -> list[str]:
    """Return resource-metadata URLs, header URL first.

    The WWW-Authenticate resource_metadata URL names the document for this
    MCP server. Path-inserted and root well-known URLs are fallbacks only.
    """
    parsed_url = URL(mcp_server_url)
    fallbacks = [
        str(
            parsed_url.with_path(
                f"{OAUTH_PROTECTED_RESOURCE_ENDPOINT}{parsed_url.path}"
            )
        ),
        str(parsed_url.with_path(OAUTH_PROTECTED_RESOURCE_ENDPOINT)),
    ]
    urls: list[str] = []
    if auth_url:
        urls.append(auth_url)
    for url in fallbacks:
        if url not in urls:
            urls.append(url)
    return urls


def _resource_metadata_from_document(
    data: Any, mcp_server_url: str
) -> ResourceMetadata | None:
    """Return metadata when the document's resource is this MCP server."""
    if not isinstance(data, Mapping):
        return None
    authorization_servers = data.get("authorization_servers")
    resource = data.get("resource")
    if (
        not authorization_servers
        or not isinstance(authorization_servers, list)
        or not resource
        or resource != mcp_server_url
    ):
        return None
    return ResourceMetadata(
        authorization_servers=authorization_servers,
        supported_scopes=data.get("scopes_supported"),
    )


async def async_discover_protected_resource(
    hass: HomeAssistant,
    auth_url: str,
    mcp_server_url: str,
) -> ResourceMetadata:
    """Discover the OAuth configuration for a protected resource.

    This is for MCP spec version 2025-11-25+. It implements the
    functionality in the MCP spec for discovery. We use the information
    from the WWW-Authenticate header to fetch the resource metadata
    implementing RFC9728.

    The header URL is fetched on its own before any well-known fallback.
    For https://example.com/public/mcp the fallbacks are:
    - https://example.com/.well-known/oauth-protected-resource/public/mcp
    - https://example.com/.well-known/oauth-protected-resource

    A document whose resource is not exactly the MCP server URL is ignored
    so a root document for a different path cannot win the discovery race.
    """
    last_error: Exception | None = None
    saw_invalid = False
    for url in _protected_resource_urls(auth_url, mcp_server_url):
        try:
            response = await _async_fetch_any(hass, [url])
        except NotFoundError:
            continue
        except TimeoutConnectError as err:
            last_error = err
            continue
        except CannotConnect as err:
            last_error = err
            continue
        try:
            data = response.json()
        except ValueError:
            saw_invalid = True
            _LOGGER.debug("OAuth resource metadata from %s was not JSON", url)
            continue
        if (metadata := _resource_metadata_from_document(data, mcp_server_url)) is None:
            saw_invalid = True
            _LOGGER.debug(
                "Ignoring OAuth resource metadata from %s for %s",
                url,
                mcp_server_url,
            )
            continue
        return metadata

    if last_error is not None and not saw_invalid:
        raise last_error
    _LOGGER.error("Invalid OAuth resource metadata for %s", mcp_server_url)
    raise CannotConnect("OAuth resource metadata is invalid")


def _authorization_server_discovery_paths(auth_server_url: URL) -> list[str]:
    """Return the list of paths to try for OAuth server discovery.

    For an auth server url with path components, e.g., https://auth.example.com/tenant1
    clients try endpoints in the following priority order:
    - OAuth 2.0 Authorization Server Metadata with path insertion:
      https://auth.example.com/.well-known/oauth-authorization-server/tenant1
    - OpenID Connect Discovery 1.0 with path insertion:
        https://auth.example.com/.well-known/openid-configuration/tenant1
    - OpenID Connect Discovery 1.0 path appending:
        https://auth.example.com/tenant1/.well-known/openid-configuration

    For an auth server url without path components, e.g., https://auth.example.com
    clients try:
    - OAuth 2.0 Authorization Server Metadata:
        https://auth.example.com/.well-known/oauth-authorization-server
    - OpenID Connect Discovery 1.0:
        https://auth.example.com/.well-known/openid-configuration
    """
    if auth_server_url.path and auth_server_url.path != "/":
        return [
            f"/.well-known/oauth-authorization-server{auth_server_url.path}",
            f"/.well-known/openid-configuration{auth_server_url.path}",
            f"{auth_server_url.path}/.well-known/openid-configuration",
        ]
    return [
        "/.well-known/oauth-authorization-server",
        "/.well-known/openid-configuration",
    ]


def _string_list(data: Mapping[str, Any], key: str) -> list[str] | None:
    """Return a string list, or None when the key is omitted.

    RFC 8414 treats a missing token_endpoint_auth_methods_supported as
    client_secret_basic. An explicit null, a non-list, or a mixed list is
    not that default, so it becomes an empty list and registration fails.
    """
    if key not in data:
        return None
    value = data[key]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return []


def _select_scopes(
    auth_header: AuthenticateHeader | None,
    oauth_config: OAuthConfig,
    resource_metadata: ResourceMetadata | None,
) -> list[str] | None:
    """Select OAuth scopes based on the MCP spec scope selection strategy.

    This follows the MCP spec strategy of preferring first the authenticate header,
    then the protected resource metadata, then finally the default scopes from
    the OAuth discovery.
    """
    if auth_header and auth_header.scopes:
        return auth_header.scopes
    if resource_metadata and resource_metadata.supported_scopes:
        return resource_metadata.supported_scopes
    return oauth_config.scopes


class InvalidUrl(HomeAssistantError):
    """Error to indicate the URL format is invalid."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class TimeoutConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class NotFoundError(CannotConnect):
    """Error to indicate the resource was not found."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

    def __init__(self, metadata: AuthenticateHeader | None = None) -> None:
        """Initialize the error."""
        super().__init__()
        self.metadata = metadata


class MissingCapabilities(HomeAssistantError):
    """Error to indicate that the MCP server is missing required capabilities."""
