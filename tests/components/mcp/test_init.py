"""Tests for the Model Context Protocol component."""

import asyncio
from collections.abc import AsyncIterator, Generator
import json
import re
import ssl
from typing import Any
from unittest.mock import Mock, patch

import httpx2
from mcp.types import (
    CallToolResult,
    ErrorData,
    Implementation,
    InitializeResult,
    ListToolsResult,
    ServerCapabilities,
    TextContent,
    Tool,
    ToolAnnotations,
    ToolsCapability,
)
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
import respx

from homeassistant.components.mcp.const import CONF_SLUG, DOMAIN
from homeassistant.components.mcp.coordinator import create_mcp_httpx_client
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import llm
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.helpers.httpx_client import SERVER_SOFTWARE

from .conftest import MCP_SERVER_URL, TEST_API_NAME

SEARCH_MEMORY_TOOL = Tool(
    name="search_memory",
    description="Search memory for relevant context based on a query.",
    inputSchema={
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {
                "type": "string",
                "description": "A free text query to search context for.",
            }
        },
    },
)
SAVE_MEMORY_TOOL = Tool(
    name="save_memory",
    description="Save a memory context.",
    inputSchema={
        "type": "object",
        "required": ["context"],
        "properties": {
            "context": {
                "type": "object",
                "description": "The context to save.",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "The key for the context.",
                    },
                },
            },
        },
    },
)


def create_llm_context() -> llm.LLMContext:
    """Create a test LLM context."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


class _SseStream(httpx2.AsyncByteStream):
    """SSE byte stream backed by an asyncio queue."""

    def __init__(self, queue: asyncio.Queue[bytes]) -> None:
        """Initialize the SSE stream."""
        self._queue = queue

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Yield SSE endpoint and message events."""
        yield b"event: endpoint\ndata: /messages\n\n"
        while True:
            yield await self._queue.get()


class FakeMcpServer:
    """Fake MCP server speaking Streamable HTTP and SSE JSON-RPC over respx."""

    def __init__(self) -> None:
        """Initialize the fake MCP server."""
        self.tools: list[Tool] = [SEARCH_MEMORY_TOOL]
        self.call_tool_result: CallToolResult = CallToolResult(
            content=[TextContent(type="text", text="OK")]
        )
        self.streamable_http_error: httpx2.Response | Exception | ErrorData | None = (
            None
        )
        self.sse_error: httpx2.Response | Exception | ErrorData | None = None
        self.list_tools_error: httpx2.Response | Exception | ErrorData | None = None
        self.call_tool_error: httpx2.Response | Exception | ErrorData | None = None
        self._sse_queue: asyncio.Queue[bytes] = asyncio.Queue()

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        """Handle an incoming MCP Streamable HTTP POST request."""
        if self.streamable_http_error is not None:
            return self._resolve_error(request, self.streamable_http_error)
        return self._dispatch_jsonrpc(request)

    def handle_sse(self, request: httpx2.Request) -> httpx2.Response:
        """Handle an incoming MCP SSE GET connection."""
        if self.sse_error is not None and not isinstance(self.sse_error, ErrorData):
            if isinstance(self.sse_error, Exception):
                raise self.sse_error
            return self.sse_error
        return httpx2.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            stream=_SseStream(self._sse_queue),
        )

    def handle_sse_message(self, request: httpx2.Request) -> httpx2.Response:
        """Handle an incoming MCP SSE POST message and push response to SSE stream."""
        if isinstance(self.sse_error, ErrorData):
            response = self._resolve_error(request, self.sse_error)
        else:
            response = self._dispatch_jsonrpc(request)
        if response.status_code == 200:
            self._sse_queue.put_nowait(
                f"event: message\ndata: {response.text}\n\n".encode()
            )
            return httpx2.Response(202)
        return response

    def _dispatch_jsonrpc(self, request: httpx2.Request) -> httpx2.Response:
        """Dispatch an incoming MCP JSON-RPC request."""
        body = json.loads(request.content)
        method = body.get("method")
        request_id = body.get("id")

        if method == "initialize":
            result = InitializeResult(
                protocolVersion="2025-03-26",
                capabilities=ServerCapabilities(tools=ToolsCapability()),
                serverInfo=Implementation(name=TEST_API_NAME, version="1.0.0"),
            )
            return self._jsonrpc_result(request_id, result)

        if method == "notifications/initialized":
            return httpx2.Response(202)

        if method == "tools/list":
            if self.list_tools_error is not None:
                return self._resolve_error(request, self.list_tools_error)
            return self._jsonrpc_result(request_id, ListToolsResult(tools=self.tools))

        if method == "tools/call":
            if self.call_tool_error is not None:
                return self._resolve_error(request, self.call_tool_error)
            return self._jsonrpc_result(request_id, self.call_tool_result)

        return httpx2.Response(400)

    def _resolve_error(
        self,
        request: httpx2.Request,
        error: httpx2.Response | Exception | ErrorData,
    ) -> httpx2.Response:
        """Resolve an error setting into a raised exception or HTTP response."""
        if isinstance(error, Exception):
            raise error
        if isinstance(error, ErrorData):
            body = json.loads(request.content)
            return self._jsonrpc_error(body.get("id"), error)
        return error

    @staticmethod
    def _jsonrpc_result(request_id: Any, result: Any) -> httpx2.Response:
        """Format a Pydantic MCP result model as a JSON-RPC 2.0 HTTP response."""
        return httpx2.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result.model_dump(
                    by_alias=True, exclude_none=True, exclude_unset=True
                ),
            },
        )

    @staticmethod
    def _jsonrpc_error(request_id: Any, error: ErrorData) -> httpx2.Response:
        """Format an MCP ErrorData model as a JSON-RPC 2.0 HTTP response."""
        return httpx2.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": error.model_dump(
                    by_alias=True, exclude_none=True, exclude_unset=True
                ),
            },
        )


@pytest.fixture
def fake_mcp_server() -> Generator[FakeMcpServer]:
    """Fixture to mock a Streamable HTTP MCP server using respx."""
    server = FakeMcpServer()
    with respx.mock:
        respx.post(url__startswith="http://1.1.1.1").mock(
            side_effect=server.handle_request
        )
        yield server


@pytest.fixture
def fake_sse_mcp_server() -> Generator[FakeMcpServer]:
    """Fixture to mock an SSE MCP server using respx."""
    server = FakeMcpServer()
    server.streamable_http_error = httpx2.Response(405)
    with respx.mock:
        respx.post("http://1.1.1.1/messages").mock(
            side_effect=server.handle_sse_message
        )
        respx.get("http://1.1.1.1/sse").mock(side_effect=server.handle_sse)
        respx.post("http://1.1.1.1/sse").mock(side_effect=server.handle_request)
        yield server


@pytest.mark.usefixtures("fake_mcp_server")
async def test_init(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the integration is initialized and can be unloaded cleanly."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "error",
    [
        httpx2.TimeoutException("Some timeout"),
        httpx2.Response(500),
        httpx2.HTTPError("Some HTTP error"),
        ErrorData(code=-32603, message="Internal error"),
    ],
)
async def test_mcp_server_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
    error: httpx2.Response | Exception | ErrorData,
) -> None:
    """Test the integration fails to setup if the server fails initialization.

    This tests generic failure types that are independent of transport.
    """
    fake_mcp_server.streamable_http_error = error

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@respx.mock
async def test_mcp_server_setup_auth_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup auth failure triggers reauth."""
    respx.post(config_entry.data[CONF_URL]).mock(return_value=httpx2.Response(401))
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@respx.mock
async def test_mcp_server_setup_auth_failure_with_www_authenticate_header(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup auth failure with WWW-Authenticate header parses header and triggers reauth."""
    headers = {
        "WWW-Authenticate": 'mcp resource_metadata="https://example.com/custom-discovery", scope="read write"'
    }
    respx.post(config_entry.data[CONF_URL]).mock(
        return_value=httpx2.Response(401, headers=headers)
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    # Get the flow handler instance and verify it has the correct auth_header
    flow_handler = hass.config_entries.flow._progress[flows[0]["flow_id"]]
    assert flow_handler.auth_header is not None
    assert (
        flow_handler.auth_header.resource_metadata_url
        == "https://example.com/custom-discovery"
    )


@respx.mock
async def test_mcp_server_http_transport_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test the integration fails to setup if the HTTP transport fails."""
    respx.post(config_entry.data[CONF_URL]).mock(
        side_effect=httpx2.ConnectError("Connection failed")
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "error",
    [
        httpx2.ConnectError("Connection failed"),
        ErrorData(code=-32603, message="Internal error"),
    ],
)
async def test_mcp_server_sse_transport_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_sse_mcp_server: FakeMcpServer,
    error: Exception | ErrorData,
) -> None:
    """Test the integration fails to setup if the SSE transport fails.

    This exercises the case where the HTTP transport fails with method not
    allowed, indicating an SSE server, then also fails with SSE.
    """
    fake_sse_mcp_server.sse_error = error
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("status_code", [405, 404])
async def test_mcp_client_fallback_to_sse_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_sse_mcp_server: FakeMcpServer,
    status_code: int,
) -> None:
    """Test mcp_client falls back to SSE on some errors.

    This exercises the backwards compatibility part of the MCP Transport
    specification.
    """
    fake_sse_mcp_server.streamable_http_error = httpx2.Response(status_code)

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


@respx.mock
@pytest.mark.usefixtures("credential")
async def test_mcp_server_authentication_failure(
    hass: HomeAssistant,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test the integration fails to setup if the server fails authentication."""
    post_route = respx.post(MCP_SERVER_URL).mock(return_value=httpx2.Response(401))

    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    assert config_entry_with_auth.state is ConfigEntryState.SETUP_ERROR
    assert post_route.calls.last.request.headers["Authorization"] == (
        "Bearer test-access-token"
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize(
    "error",
    [
        httpx2.Response(500),
        httpx2.Response(404),
        httpx2.Response(405),
        ErrorData(code=-32603, message="Internal error"),
    ],
)
async def test_list_tools_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
    error: httpx2.Response | ErrorData,
) -> None:
    """Test the integration fails to load if the first data fetch returns an error."""
    fake_mcp_server.list_tools_error = error

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_llm_get_api_tools(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
) -> None:
    """Test MCP tools are returned as LLM API tools."""
    fake_mcp_server.tools = [SEARCH_MEMORY_TOOL, SAVE_MEMORY_TOOL]

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    assert api

    api_instance = await api.async_get_api_instance(create_llm_context())
    assert len(api_instance.tools) == 2
    tool = api_instance.tools[0]
    assert tool.name == "search_memory"
    assert tool.description == "Search memory for relevant context based on a query."
    with pytest.raises(
        probatio.Invalid, match=re.escape("required key not provided at 'query'")
    ):
        tool.parameters({})
    assert tool.parameters({"query": "frogs"}) == {"query": "frogs"}

    tool = api_instance.tools[1]
    assert tool.name == "save_memory"
    assert tool.description == "Save a memory context."
    with pytest.raises(
        probatio.Invalid, match=re.escape("required key not provided at 'context'")
    ):
        tool.parameters({})
    assert tool.parameters({"context": {"fact": "User was born in February"}}) == {
        "context": {"fact": "User was born in February"}
    }


@pytest.mark.parametrize(
    ("remote_annotations", "expected_annotations"),
    [
        pytest.param(None, llm.ToolAnnotations(), id="unannotated"),
        pytest.param(
            ToolAnnotations(readOnlyHint=True, openWorldHint=False),
            llm.ToolAnnotations(read_only=True, open_world=False),
            id="partly-annotated",
        ),
        pytest.param(
            ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=True,
            ),
            llm.ToolAnnotations(destructive=False, idempotent=True),
            id="fully-annotated",
        ),
    ],
)
async def test_llm_tool_annotations(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
    remote_annotations: ToolAnnotations | None,
    expected_annotations: llm.ToolAnnotations,
) -> None:
    """Test the annotations the remote server declares are carried over."""
    fake_mcp_server.tools = [
        SEARCH_MEMORY_TOOL.model_copy(
            update={"title": "Search memory", "annotations": remote_annotations}
        )
    ]

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    api = next(
        iter(api for api in llm.async_get_apis(hass) if api.name == TEST_API_NAME)
    )
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    assert tool.integration == "mcp"
    assert tool.title == "Search memory"
    assert tool.annotations == expected_annotations


@pytest.mark.parametrize(
    ("call_tool_result", "expected_result"),
    [
        pytest.param(
            CallToolResult(
                content=[TextContent(type="text", text="User was born in February")]
            ),
            llm.ToolResult(
                data={
                    "content": [{"text": "User was born in February", "type": "text"}]
                }
            ),
            id="success",
        ),
        pytest.param(
            CallToolResult(
                content=[TextContent(type="text", text="Memory search failed")],
                isError=True,
            ),
            llm.ToolResult(
                data={
                    "content": [{"text": "Memory search failed", "type": "text"}],
                    "isError": True,
                },
                error=True,
            ),
            id="error",
        ),
    ],
)
async def test_call_tool(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
    call_tool_result: CallToolResult,
    expected_result: llm.ToolResult,
) -> None:
    """Test calling an MCP Tool through the LLM API."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    assert api

    api_instance = await api.async_get_api_instance(create_llm_context())
    assert len(api_instance.tools) == 1
    tool = api_instance.tools[0]
    assert tool.name == "search_memory"

    fake_mcp_server.call_tool_result = call_tool_result
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool_name="search_memory", tool_args={"query": "User's birth month"}
        ),
        create_llm_context(),
    )
    assert result == expected_result


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (httpx2.Response(500), "Error when calling tool: Server error"),
        (httpx2.Response(404), "Error when calling tool: Client error '404 Not Found'"),
        (
            httpx2.Response(405),
            "Error when calling tool: Client error '405 Method Not Allowed'",
        ),
        (
            ErrorData(code=-32603, message="Tool execution error"),
            "Error communicating with MCP server when calling tool: Tool execution error",
        ),
    ],
)
async def test_call_tool_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
    error: httpx2.Response | ErrorData,
    expected_message: str,
) -> None:
    """Test handling an MCP Tool call failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    assert api

    api_instance = await api.async_get_api_instance(create_llm_context())
    assert len(api_instance.tools) == 1
    tool = api_instance.tools[0]
    assert tool.name == "search_memory"

    fake_mcp_server.call_tool_error = error
    with pytest.raises(HomeAssistantError, match=expected_message):
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="search_memory", tool_args={"query": "User's birth month"}
            ),
            create_llm_context(),
        )


@pytest.mark.usefixtures("fake_mcp_server")
async def test_convert_tool_schema_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test a failure converting an MCP tool schema to a Home Assistant schema."""
    with patch(
        "homeassistant.components.mcp.coordinator.from_openapi",
        side_effect=ValueError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    with patch(
        "homeassistant.components.mcp.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
        await hass.async_block_till_done()

    assert config_entry_with_auth.state is ConfigEntryState.SETUP_RETRY


async def test_tool_call_no_auth_auth_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
) -> None:
    """Test tool call auth failure when no auth was initially required."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    fake_mcp_server.call_tool_error = httpx2.Response(401)

    with pytest.raises(ConfigEntryAuthFailed):
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="search_memory", tool_args={"query": "User's birth month"}
            ),
            create_llm_context(),
        )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_tool_call_no_auth_auth_failure_with_www_authenticate_header(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
) -> None:
    """Test tool call 401 with WWW-Authenticate header triggers reauth and passes header."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    headers = {
        "WWW-Authenticate": 'mcp resource_metadata="https://example.com/custom-discovery", scope="read write"'
    }
    fake_mcp_server.call_tool_error = httpx2.Response(401, headers=headers)

    with pytest.raises(ConfigEntryAuthFailed):
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="search_memory", tool_args={"query": "User's birth month"}
            ),
            create_llm_context(),
        )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    # Get the flow handler instance and verify it has the correct auth_header
    flow_handler = hass.config_entries.flow._progress[flows[0]["flow_id"]]
    assert flow_handler.auth_header is not None
    assert (
        flow_handler.auth_header.resource_metadata_url
        == "https://example.com/custom-discovery"
    )


@pytest.mark.usefixtures("credential", "fake_mcp_server")
async def test_tool_call_expired_oauth_failure(
    hass: HomeAssistant,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test tool call token refresh failure when OAuth is configured."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    assert config_entry_with_auth.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    # Mock token validation failure during tool call
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
            side_effect=OAuth2TokenRequestReauthError(
                request_info=Mock(), history=(), domain=DOMAIN
            ),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="search_memory", tool_args={"query": "User's birth month"}
            ),
            create_llm_context(),
        )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.usefixtures("credential")
async def test_mcp_server_setup_oauth_failure(
    hass: HomeAssistant,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test setup OAuth failure triggers reauth."""
    # Mock token validation failure (e.g. refresh token expired)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=OAuth2TokenRequestReauthError(
            request_info=Mock(), history=(), domain=DOMAIN
        ),
    ):
        await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
        assert config_entry_with_auth.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("Listing tools timed out"),
        httpx2.TimeoutException("Listing tools timed out"),
    ],
)
async def test_list_tools_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
    error: Exception,
) -> None:
    """Test setup fails with SETUP_RETRY if list tools times out."""
    fake_mcp_server.list_tools_error = error

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("Call timed out"),
        httpx2.TimeoutException("Call timed out"),
    ],
)
async def test_tool_call_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
    error: Exception,
) -> None:
    """Test tool call timing out raises HomeAssistantError."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    fake_mcp_server.call_tool_error = error

    with pytest.raises(HomeAssistantError, match="Timeout when calling tool"):
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="search_memory", tool_args={"query": "User's birth month"}
            ),
            create_llm_context(),
        )


@pytest.mark.usefixtures("credential", "fake_mcp_server")
async def test_tool_call_transient_oauth_failure(
    hass: HomeAssistant,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test tool call transient token refresh failure does not trigger reauth."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    assert config_entry_with_auth.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    # Mock transient token validation failure (e.g. 503 Service Unavailable)
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
            side_effect=OAuth2TokenRequestError(
                request_info=Mock(), history=(), domain=DOMAIN
            ),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="search_memory", tool_args={"query": "User's birth month"}
            ),
            create_llm_context(),
        )

    # Verify no reauth flow is initiated
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


@pytest.mark.usefixtures("credential")
async def test_mcp_server_setup_transient_oauth_failure(
    hass: HomeAssistant,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test setup transient OAuth failure does not trigger reauth."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=OAuth2TokenRequestError(
            request_info=Mock(), history=(), domain=DOMAIN
        ),
    ):
        await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
        assert config_entry_with_auth.state is ConfigEntryState.SETUP_RETRY

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


async def test_tool_call_http_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_mcp_server: FakeMcpServer,
) -> None:
    """Test tool call HTTP error raises HomeAssistantError."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    fake_mcp_server.call_tool_error = httpx2.HTTPError("Connection timed out or failed")

    with pytest.raises(
        HomeAssistantError,
        match="Error communicating with MCP server when calling tool",
    ):
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="search_memory", tool_args={"query": "User's birth month"}
            ),
            create_llm_context(),
        )


@pytest.mark.usefixtures("fake_sse_mcp_server")
async def test_sse_client_does_not_build_ssl_context(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test the SSE transport does not load certificates in the event loop."""
    with patch.object(ssl.SSLContext, "load_verify_locations") as mock_load_certs:
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED
    assert not mock_load_certs.called


@pytest.mark.usefixtures("fake_mcp_server")
async def test_streamable_http_client_closed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test the httpx client passed to the streamable HTTP transport.

    It identifies as Home Assistant and is closed once the client exits.
    """
    created_clients: list[httpx2.AsyncClient] = []

    def wrap_create_client(**kwargs: Any) -> httpx2.AsyncClient:
        client = create_mcp_httpx_client(**kwargs)
        created_clients.append(client)
        return client

    with patch(
        "homeassistant.components.mcp.coordinator.create_mcp_httpx_client",
        side_effect=wrap_create_client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    assert len(created_clients) == 1
    http_client = created_clients[0]
    assert http_client.headers["User-Agent"] == SERVER_SOFTWARE
    assert http_client.is_closed


@pytest.mark.usefixtures("fake_mcp_server")
async def test_llm_api_id(hass: HomeAssistant) -> None:
    """Test the LLM API id of a discovered server survives a reinstall of the app."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://1.1.1.1/mcp", CONF_SLUG: "a0d7b954_mcp"},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    assert api.id == "mcp-a0d7b954_mcp"

    await hass.config_entries.async_remove(config_entry.entry_id)

    # Reinstalling the app discovers the server again as a new config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://1.1.1.1/mcp", CONF_SLUG: "a0d7b954_mcp"},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    assert api.id == "mcp-a0d7b954_mcp"
