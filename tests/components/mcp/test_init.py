"""Tests for the Model Context Protocol component."""

import re
from unittest.mock import AsyncMock, Mock, patch

import httpx
from mcp import McpError
from mcp.types import CallToolResult, ErrorData, ListToolsResult, TextContent, Tool
import pytest
import voluptuous as vol

from homeassistant.components.mcp.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
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

from .conftest import TEST_API_NAME

from tests.common import MockConfigEntry

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


async def test_init(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_mcp_client: Mock
) -> None:
    """Test the integration is initialized and can be unloaded cleanly."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect"),
    [
        (httpx.TimeoutException("Some timeout")),
        (httpx.HTTPStatusError("", request=None, response=httpx.Response(500))),
        (httpx.HTTPError("Some HTTP error")),
    ],
)
async def test_mcp_server_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_mcp_client: Mock,
    side_effect: Exception,
) -> None:
    """Test the integration fails to setup if the server fails initialization.

    This tests generic failure types that are independent of transport.
    """
    mock_mcp_client.side_effect = side_effect

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mcp_server_setup_auth_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_mcp_client: Mock,
) -> None:
    """Test setup auth failure triggers reauth."""
    mock_mcp_client.side_effect = httpx.HTTPStatusError(
        "Authentication required", request=None, response=httpx.Response(401)
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_mcp_server_setup_auth_failure_with_www_authenticate_header(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_mcp_client: Mock,
) -> None:
    """Test setup auth failure with WWW-Authenticate header parses header and triggers reauth."""
    headers = {
        "WWW-Authenticate": 'mcp resource_metadata="https://example.com/custom-discovery", scope="read write"'
    }
    mock_mcp_client.side_effect = httpx.HTTPStatusError(
        "Authentication required",
        request=None,
        response=httpx.Response(401, headers=headers),
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


async def test_mcp_server_http_transport_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_http_streamable_client: AsyncMock,
) -> None:
    """Test the integration fails to setup if the HTTP transport fails."""
    mock_http_streamable_client.side_effect = ExceptionGroup(
        "Connection error", [httpx.ConnectError("Connection failed")]
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mcp_server_sse_transport_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_http_streamable_client: AsyncMock,
    mock_sse_client: AsyncMock,
) -> None:
    """Test the integration fails to setup if the SSE transport fails.

    This exercises the case where the HTTP transport fails with method not
    allowed, indicating an SSE server, then also fails with SSE.
    """
    http_405 = httpx.HTTPStatusError(
        "Method not allowed", request=None, response=httpx.Response(405)
    )
    mock_http_streamable_client.side_effect = ExceptionGroup(
        "Method not allowed", [http_405]
    )

    mock_sse_client.side_effect = ExceptionGroup(
        "Connection error", [httpx.ConnectError("Connection failed")]
    )


@pytest.mark.parametrize(
    ("side_effect"),
    [
        (
            ExceptionGroup(
                "Method not allowed",
                [
                    httpx.HTTPStatusError(
                        "Method not allowed",
                        request=None,
                        response=httpx.Response(405),
                    )
                ],
            ),
        ),
        (
            ExceptionGroup(
                "Some exception group",
                [McpError(ErrorData(code=500, message="Session terminated"))],
            )
        ),
    ],
)
async def test_mcp_client_fallback_to_sse_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_http_streamable_client: AsyncMock,
    mock_sse_client: AsyncMock,
    mock_mcp_client: Mock,
    side_effect: Exception,
) -> None:
    """Test mcp_client falls back to SSE on some errors.

    This exercises the backwards compatibility part of the MCP Transport
    specification.
    """
    mock_http_streamable_client.side_effect = side_effect

    # Setup mocks for SSE fallback
    mock_sse_client.return_value.__aenter__.return_value = ("read", "write")
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    assert mock_http_streamable_client.called
    assert mock_sse_client.called


async def test_mcp_server_authentication_failure(
    hass: HomeAssistant,
    credential: None,
    config_entry_with_auth: MockConfigEntry,
    mock_mcp_client: Mock,
) -> None:
    """Test the integration fails to setup if the server fails authentication."""
    mock_mcp_client.side_effect = httpx.HTTPStatusError(
        "Authentication required", request=None, response=httpx.Response(401)
    )

    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    assert config_entry_with_auth.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_list_tools_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_mcp_client: Mock
) -> None:
    """Test the integration fails to load if the first data fetch returns an error."""
    mock_mcp_client.return_value.list_tools.side_effect = httpx.HTTPStatusError(
        "", request=None, response=httpx.Response(500)
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_llm_get_api_tools(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_mcp_client: Mock
) -> None:
    """Test MCP tools are returned as LLM API tools."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL, SAVE_MEMORY_TOOL],
    )

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
        vol.Invalid, match=re.escape("required key not provided at 'query'")
    ):
        tool.parameters({})
    assert tool.parameters({"query": "frogs"}) == {"query": "frogs"}

    tool = api_instance.tools[1]
    assert tool.name == "save_memory"
    assert tool.description == "Save a memory context."
    with pytest.raises(
        vol.Invalid, match=re.escape("required key not provided at 'context'")
    ):
        tool.parameters({})
    assert tool.parameters({"context": {"fact": "User was born in February"}}) == {
        "context": {"fact": "User was born in February"}
    }


async def test_call_tool(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_mcp_client: Mock
) -> None:
    """Test calling an MCP Tool through the LLM API."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    assert api

    api_instance = await api.async_get_api_instance(create_llm_context())
    assert len(api_instance.tools) == 1
    tool = api_instance.tools[0]
    assert tool.name == "search_memory"

    mock_mcp_client.return_value.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text="User was born in February")]
    )
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool_name="search_memory", tool_args={"query": "User's birth month"}
        ),
        create_llm_context(),
    )
    assert result == {
        "content": [{"text": "User was born in February", "type": "text"}]
    }


async def test_call_tool_fails(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_mcp_client: Mock
) -> None:
    """Test handling an MCP Tool call failure."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    assert api

    api_instance = await api.async_get_api_instance(create_llm_context())
    assert len(api_instance.tools) == 1
    tool = api_instance.tools[0]
    assert tool.name == "search_memory"

    mock_mcp_client.return_value.call_tool.side_effect = httpx.HTTPStatusError(
        "Server error", request=None, response=httpx.Response(500)
    )
    with pytest.raises(
        HomeAssistantError, match="Error when calling tool: Server error"
    ):
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="search_memory", tool_args={"query": "User's birth month"}
            ),
            create_llm_context(),
        )


async def test_convert_tool_schema_fails(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_mcp_client: Mock
) -> None:
    """Test a failure converting an MCP tool schema to a Home Assistant schema."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

    with patch(
        "homeassistant.components.mcp.coordinator.from_openapi",
        side_effect=ValueError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    config_entry_with_auth: MockConfigEntry,
    mock_mcp_client: AsyncMock,
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
    mock_mcp_client: Mock,
) -> None:
    """Test tool call auth failure when no auth was initially required."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    # Mock tool call encountering a 401 response
    mock_mcp_client.return_value.call_tool.side_effect = httpx.HTTPStatusError(
        "Authentication required", request=None, response=httpx.Response(401)
    )

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
    mock_mcp_client: Mock,
) -> None:
    """Test tool call 401 with WWW-Authenticate header triggers reauth and passes header."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    # Mock tool call encountering a 401 response with WWW-Authenticate header
    headers = {
        "WWW-Authenticate": 'mcp resource_metadata="https://example.com/custom-discovery", scope="read write"'
    }
    mock_mcp_client.return_value.call_tool.side_effect = httpx.HTTPStatusError(
        "Authentication required",
        request=None,
        response=httpx.Response(401, headers=headers),
    )

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


async def test_tool_call_expired_oauth_failure(
    hass: HomeAssistant,
    credential: None,
    config_entry_with_auth: MockConfigEntry,
    mock_mcp_client: Mock,
) -> None:
    """Test tool call token refresh failure when OAuth is configured."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

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


async def test_mcp_server_setup_oauth_failure(
    hass: HomeAssistant,
    credential: None,
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


async def test_list_tools_timeout(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_mcp_client: Mock
) -> None:
    """Test setup fails with SETUP_RETRY if list tools times out."""
    mock_mcp_client.return_value.list_tools.side_effect = TimeoutError(
        "Listing tools timed out"
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_tool_call_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_mcp_client: Mock,
) -> None:
    """Test tool call timing out raises HomeAssistantError."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    # Mock tool call timeout
    mock_mcp_client.return_value.call_tool.side_effect = TimeoutError("Call timed out")

    with pytest.raises(HomeAssistantError, match="Timeout when calling tool"):
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="search_memory", tool_args={"query": "User's birth month"}
            ),
            create_llm_context(),
        )


async def test_tool_call_transient_oauth_failure(
    hass: HomeAssistant,
    credential: None,
    config_entry_with_auth: MockConfigEntry,
    mock_mcp_client: Mock,
) -> None:
    """Test tool call transient token refresh failure does not trigger reauth."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

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


async def test_mcp_server_setup_transient_oauth_failure(
    hass: HomeAssistant,
    credential: None,
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
    mock_mcp_client: Mock,
) -> None:
    """Test tool call HTTP error raises HomeAssistantError."""
    mock_mcp_client.return_value.list_tools.return_value = ListToolsResult(
        tools=[SEARCH_MEMORY_TOOL]
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    apis = llm.async_get_apis(hass)
    api = next(iter([api for api in apis if api.name == TEST_API_NAME]))
    api_instance = await api.async_get_api_instance(create_llm_context())
    tool = api_instance.tools[0]

    # Mock tool call raising HTTPError
    mock_mcp_client.return_value.call_tool.side_effect = httpx.HTTPError(
        "Connection timed out or failed"
    )

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
