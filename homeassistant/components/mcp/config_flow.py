"""Config flow for the Model Context Protocol integration."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import logging
import re
from typing import Any, cast

import httpx
import voluptuous as vol
from yarl import URL

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    async_get_implementations,
)

from . import async_get_config_entry_implementation
from .application_credentials import authorization_server_context
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_AUTHORIZATION_URL,
    CONF_SCOPE,
    CONF_TOKEN_URL,
    DOMAIN,
)
from .coordinator import TokenManager, mcp_client

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
    }
)

# Headers and regex for WWW-Authenticate parsing for rfc9728
WWW_AUTHENTICATE_HEADER = "WWW-Authenticate"
RESOURCE_METADATA_REGEXP = r'resource_metadata="([^"]+)"'
OAUTH_PROTECTED_RESOURCE_ENDPOINT = "/.well-known/oauth-protected-resource"
SCOPES_REGEXP = r'scope="([^"]+)"'


@dataclass
class AuthenticateHeader:
    """Class to hold info from the WWW-Authenticate header for supporting rfc9728."""

    resource_metadata_url: str
    scopes: list[str] | None = None

    @classmethod
    def from_header(
        cls, url: str, error_response: httpx.Response
    ) -> AuthenticateHeader | None:
        """Create AuthenticateHeader from WWW-Authenticate header."""
        if not (header := error_response.headers.get(WWW_AUTHENTICATE_HEADER)) or not (
            match := re.search(RESOURCE_METADATA_REGEXP, header)
        ):
            return None
        resource_metadata_url = str(URL(url).join(URL(match.group(1))))
        scope_match = re.search(SCOPES_REGEXP, header)
        return cls(
            resource_metadata_url=resource_metadata_url,
            scopes=scope_match.group(1).split(" ") if scope_match else None,
        )


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
    return OAuthConfig(
        authorization_server=AuthorizationServer(
            authorize_url=authorize_url,
            token_url=token_url,
        ),
        scopes=scopes,
    )


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], token_manager: TokenManager | None = None
) -> dict[str, Any]:
    """Validate the user input and connect to the MCP server."""
    url = data[CONF_URL]
    try:
        cv.url(url)  # Cannot be added to schema directly
    except vol.Invalid as error:
        raise InvalidUrl from error
    try:
        async with mcp_client(hass, url, token_manager=token_manager) as session:
            response = await session.initialize()
    except httpx.TimeoutException as error:
        _LOGGER.info("Timeout connecting to MCP server: %s", error)
        raise TimeoutConnectError from error
    except httpx.HTTPStatusError as error:
        _LOGGER.info("Cannot connect to MCP server: %s", error)
        if error.response.status_code == 401:
            auth_header = AuthenticateHeader.from_header(url, error.response)
            raise InvalidAuth(auth_header) from error
        raise CannotConnect from error
    except httpx.HTTPError as error:
        _LOGGER.info("Cannot connect to MCP server: %s", error)
        raise CannotConnect from error

    if not response.capabilities.tools:
        raise MissingCapabilities(
            f"MCP Server {url} does not support 'Tools' capability"
        )

    return {"title": response.serverInfo.name}


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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
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
                self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"example_url": EXAMPLE_URL},
        )

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
                    # Use the first authorization server from the resource metadata as it
                    # is the most common to have only one and there is not a defined strategy.
                    resource_metadata.authorization_servers[0],
                )
            else:
                _LOGGER.debug(
                    "Discovering authorization server without protected resource metadata"
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
                    CONF_AUTHORIZATION_URL: oauth_config.authorization_server.authorize_url,
                    CONF_TOKEN_URL: oauth_config.authorization_server.token_url,
                    CONF_SCOPE: _select_scopes(
                        self.auth_header, oauth_config, resource_metadata
                    ),
                }
            )
            return await self.async_step_credentials_choice()

    def authorization_server(self) -> AuthorizationServer:
        """Return the authorization server provided by the MCP server."""
        return AuthorizationServer(
            self.data[CONF_AUTHORIZATION_URL],
            self.data[CONF_TOKEN_URL],
        )

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        data = {}
        if self.data and (scopes := self.data[CONF_SCOPE]) is not None:
            data[CONF_SCOPE] = " ".join(scopes)
        data.update(super().extra_authorize_data)
        return data

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

    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pick implementation step.

        This exists to dynamically set application credentials Authorization Server
        based on the values form the OAuth discovery step.
        """
        with authorization_server_context(self.authorization_server()):
            return await super().async_step_pick_implementation(user_input)

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

        # Unique id based on the application credentials OAuth Client ID
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=config_entry_data
            )
        await self.async_set_unique_id(config_entry_data["auth_implementation"])
        return self.async_create_entry(
            title=info["title"],
            data=config_entry_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        config_entry = self._get_reauth_entry()
        self.data = {**config_entry.data}
        self.flow_impl = await async_get_config_entry_implementation(  # type: ignore[assignment]
            self.hass, config_entry
        )
        return await self.async_step_auth()


async def _async_fetch_any(
    hass: HomeAssistant,
    urls: Iterable[str],
) -> httpx.Response:
    """Fetch all URLs concurrently and return the first successful response."""

    async def fetch(url: str) -> httpx.Response:
        _LOGGER.debug("Fetching URL %s", url)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response
        except httpx.TimeoutException as error:
            _LOGGER.debug("Timeout fetching URL %s: %s", url, error)
            raise TimeoutConnectError from error
        except httpx.HTTPStatusError as error:
            _LOGGER.debug("Server error for URL %s: %s", url, error)
            if error.response.status_code == 404:
                raise NotFoundError from error
            raise CannotConnect from error
        except httpx.HTTPError as error:
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


async def async_discover_protected_resource(
    hass: HomeAssistant,
    auth_url: str,
    mcp_server_url: str,
) -> ResourceMetadata:
    """Discover the OAuth configuration for a protected resource for MCP spec version 2025-11-25+.

    This implements the functionality in the MCP spec for discovery. We use the information
    from the WWW-Authenticate header to fetch the resource metadata implementing
    RFC9728.

    For the url https://example.com/public/mcp we attempt these urls:
    - https://example.com/.well-known/oauth-protected-resource/public/mcp
    - https://example.com/.well-known/oauth-protected-resource
    """
    parsed_url = URL(mcp_server_url)
    urls_to_try = {
        auth_url,
        str(
            parsed_url.with_path(
                f"{OAUTH_PROTECTED_RESOURCE_ENDPOINT}{parsed_url.path}"
            )
        ),
        str(parsed_url.with_path(OAUTH_PROTECTED_RESOURCE_ENDPOINT)),
    }

    response = await _async_fetch_any(hass, list(urls_to_try))

    # Parse the OAuth Authorization Protected Resource Metadata (rfc9728). We
    # expect to find at least one authorization server in the response and
    # a valid resource field that matches the MCP server URL.
    data = response.json()
    if (
        not (authorization_servers := data.get("authorization_servers"))
        or not (resource := data.get("resource"))
        or (resource != mcp_server_url)
    ):
        _LOGGER.error("Invalid OAuth resource metadata: %s", data)
        raise CannotConnect("OAuth resource metadata is invalid")
    return ResourceMetadata(
        authorization_servers=authorization_servers,
        supported_scopes=data.get("scopes_supported"),
    )


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
