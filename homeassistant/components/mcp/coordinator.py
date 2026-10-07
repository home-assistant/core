"""Types for the Model Context Protocol integration."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
import datetime
import logging
from typing import override

import httpx  # noqa: TID251
import httpx2
from mcp import McpError
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import InitializeResult, ToolAnnotations
import probatio

# Imported by name because the tests patch it on this module.
from probatio import from_openapi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import llm
from homeassistant.helpers.httpx_client import create_async_httpx_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.ssl import SSL_ALPN_HTTP11, SSLCipherList, client_context

from .auth import AuthenticateHeader
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = datetime.timedelta(minutes=30)
TIMEOUT = 10

type TokenManager = Callable[[], Awaitable[str]]


def _iter_wrapped_errors(exc: BaseException) -> Iterator[BaseException]:
    """Yield an exception and errors nested in groups or causes."""
    seen: set[int] = set()
    stack = [exc]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, BaseExceptionGroup):
            stack.extend(reversed(current.exceptions))
            if current.__cause__ is not None:
                stack.append(current.__cause__)
            continue
        yield current
        if current.__cause__ is not None:
            stack.append(current.__cause__)


def _representative_mcp_error(exc: BaseException) -> BaseException:
    """Pick the transport error callers should handle.

    anyio wraps the SDK's httpx.HTTPStatusError in an ExceptionGroup. A 401
    has to stay an auth failure instead of being reported as an unknown error.
    Home Assistant aliases httpx to httpx2, so those errors are already httpx2.
    """
    status_error: BaseException | None = None
    mcp_error: BaseException | None = None
    http_error: BaseException | None = None
    fallback: BaseException | None = None
    for nested in _iter_wrapped_errors(exc):
        if fallback is None:
            fallback = nested
        if status_error is None and isinstance(nested, httpx2.HTTPStatusError):
            status_error = nested
        elif mcp_error is None and isinstance(nested, McpError):
            mcp_error = nested
        elif http_error is None and isinstance(nested, httpx2.HTTPError):
            http_error = nested
    if status_error is not None:
        return status_error
    if mcp_error is not None:
        return mcp_error
    if http_error is not None:
        return http_error
    return fallback if fallback is not None else exc


def _create_sse_httpx_client(
    headers: dict[str, str] | None = None,
    timeout: httpx2.Timeout | None = None,
    auth: httpx2.Auth | None = None,
) -> httpx2.AsyncClient:
    """Create the httpx client used by the SSE transport.

    The SSE transport closes the client itself, so it cannot be handed one of
    the Home Assistant managed clients. Building it here keeps it off the SDK
    default, which reads the CA bundle from disk inside the event loop.
    """
    return httpx2.AsyncClient(
        verify=client_context(SSLCipherList.PYTHON_DEFAULT, SSL_ALPN_HTTP11),
        follow_redirects=True,
        headers=headers,
        timeout=timeout,
        auth=auth,
    )


@asynccontextmanager
async def mcp_client(
    hass: HomeAssistant,
    url: str,
    token_manager: TokenManager | None = None,
) -> AsyncGenerator[tuple[ClientSession, InitializeResult]]:
    """Create an MCP client.

    This is an asynccontext manager that exists to wrap other async context managers
    so that the coordinator has a single object to manage.
    """
    headers: dict[str, str] = {}
    if token_manager is not None:
        token = await token_manager()
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with (
            streamable_http_client(
                url=url,
                http_client=create_async_httpx_client(hass, headers=headers),
            ) as (read_stream, write_stream, _),
            ClientSession(read_stream, write_stream) as session,
        ):
            result = await session.initialize()
            yield session, result
    except ExceptionGroup as streamable_err:
        main_error = _representative_mcp_error(streamable_err)
        # Method not Allowed likely means this is not a streamable HTTP server,
        # but it may be an SSE server. This is part of the MCP Transport
        # backwards compatibility specification.
        # We also handle other generic McpErrors since proxies may not respond
        # consistently with a 405.
        if (
            isinstance(main_error, httpx2.HTTPStatusError)
            and main_error.response.status_code == 405
        ) or isinstance(main_error, McpError):
            _LOGGER.debug(
                "Streamable HTTP client failed, attempting SSE client: %s", main_error
            )
            try:
                async with (
                    sse_client(
                        url=url,
                        headers=headers,
                        httpx_client_factory=_create_sse_httpx_client,
                    ) as streams,
                    ClientSession(*streams) as session,
                ):
                    result = await session.initialize()
                    yield session, result
            except ExceptionGroup as sse_err:
                _LOGGER.debug("Error creating SSE MCP client: %s", sse_err)
                raise _representative_mcp_error(sse_err) from sse_err
            except httpx.HTTPError as sse_http_err:
                # The streamable failure is context here. Report the SSE error.
                raise sse_http_err from None
        else:
            _LOGGER.debug("Error creating MCP client: %s", streamable_err)
            raise main_error from streamable_err


def _tool_annotations(remote: ToolAnnotations | None) -> llm.ToolAnnotations:
    """Return the annotations the remote server declares for a tool.

    A hint the server leaves out keeps the conservative default.
    """
    if remote is None:
        return llm.ToolAnnotations()
    declared = {
        field: value
        for field, value in (
            ("read_only", remote.readOnlyHint),
            ("destructive", remote.destructiveHint),
            ("idempotent", remote.idempotentHint),
            ("open_world", remote.openWorldHint),
        )
        if value is not None
    }
    return llm.ToolAnnotations(**declared)


class ModelContextProtocolTool(llm.Tool):
    """A Tool exposed over the Model Context Protocol."""

    integration = DOMAIN

    def __init__(
        self,
        name: str,
        title: str | None,
        description: str | None,
        parameters: probatio.Schema,
        server_url: str,
        config_entry: ConfigEntry,
        token_manager: TokenManager | None = None,
        annotations: llm.ToolAnnotations = llm.ToolAnnotations(),
    ) -> None:
        """Initialize the tool."""
        self.name = name
        self.title = title
        self.description = description
        self.parameters = parameters
        self.annotations = annotations
        self.server_url = server_url
        self.config_entry = config_entry
        self.token_manager = token_manager

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        """Call the tool."""
        try:
            async with asyncio.timeout(TIMEOUT):
                async with mcp_client(hass, self.server_url, self.token_manager) as (
                    session,
                    _,
                ):
                    result = await session.call_tool(
                        tool_input.tool_name, tool_input.tool_args
                    )
        except TimeoutError as error:
            _LOGGER.debug("Timeout when calling tool: %s", error)
            raise HomeAssistantError(f"Timeout when calling tool: {error}") from error
        except OAuth2TokenRequestReauthError as error:
            _LOGGER.debug("OAuth token request failed when calling tool: %s", error)
            self.config_entry.async_start_reauth(hass)
            raise ConfigEntryAuthFailed(
                "OAuth token request failed when calling tool"
            ) from error
        except (httpx.HTTPStatusError, httpx2.HTTPStatusError) as error:
            _LOGGER.debug("Error when calling tool: %s", error)
            if error.response.status_code == 401:
                auth_header = AuthenticateHeader.from_header(
                    self.server_url, error.response
                )
                self.config_entry.async_start_reauth(
                    hass, data={"auth_header": auth_header}
                )
                raise ConfigEntryAuthFailed(
                    "The MCP server requires authentication"
                ) from error
            raise HomeAssistantError(f"Error when calling tool: {error}") from error
        except (httpx.HTTPError, httpx2.HTTPError) as error:
            _LOGGER.debug(
                "Error communicating with MCP server when calling tool: %s", error
            )
            raise HomeAssistantError(
                f"Error communicating with MCP server when calling tool: {error}"
            ) from error
        return llm.ToolResult(
            data=result.model_dump(exclude_unset=True, exclude_none=True),
            error=bool(result.isError),
        )


class ModelContextProtocolCoordinator(DataUpdateCoordinator[list[llm.Tool]]):
    """Define an object to hold MCP data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        token_manager: TokenManager | None = None,
    ) -> None:
        """Initialize ModelContextProtocolCoordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.token_manager = token_manager

    @override
    async def _async_update_data(self) -> list[llm.Tool]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            async with asyncio.timeout(TIMEOUT):
                async with mcp_client(
                    self.hass, self.config_entry.data[CONF_URL], self.token_manager
                ) as (session, _):
                    result = await session.list_tools()
        except TimeoutError as error:
            _LOGGER.debug("Timeout when listing tools: %s", error)
            raise UpdateFailed(f"Timeout when listing tools: {error}") from error
        except OAuth2TokenRequestReauthError as error:
            _LOGGER.debug("OAuth token request failed: %s", error)
            raise ConfigEntryAuthFailed("OAuth token request failed") from error
        except (httpx.HTTPStatusError, httpx2.HTTPStatusError) as error:
            _LOGGER.debug("Error communicating with API: %s", error)
            if error.response.status_code == 401:
                auth_header = AuthenticateHeader.from_header(
                    self.config_entry.data[CONF_URL], error.response
                )
                self.config_entry.async_start_reauth(
                    self.hass, data={"auth_header": auth_header}
                )
                raise ConfigEntryAuthFailed(
                    "The MCP server requires authentication"
                ) from error
            raise UpdateFailed(f"Error communicating with API: {error}") from error
        except (httpx.HTTPError, httpx2.HTTPError) as err:
            _LOGGER.debug("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        _LOGGER.debug("Received tools: %s", result.tools)
        tools: list[llm.Tool] = []
        for tool in result.tools:
            try:
                parameters = from_openapi(tool.inputSchema)
            except Exception as err:
                raise UpdateFailed(
                    f"Error converting schema {err}: {tool.inputSchema}"
                ) from err
            tools.append(
                ModelContextProtocolTool(
                    tool.name,
                    tool.title,
                    tool.description,
                    parameters,
                    self.config_entry.data[CONF_URL],
                    self.config_entry,
                    self.token_manager,
                    _tool_annotations(tool.annotations),
                )
            )
        return tools
