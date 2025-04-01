"""Tests for the Model Context Protocol component."""

import re
from unittest.mock import Mock, patch

import httpx
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
import pytest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

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
        user_prompt="test_text",
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
        (httpx.HTTPStatusError("", request=None, response=httpx.Response(401))),
        (httpx.HTTPError("Some HTTP error")),
    ],
)
async def test_mcp_server_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_mcp_client: Mock,
    side_effect: Exception,
) -> None:
    """Test the integration fails to setup if the server fails initialization."""
    mock_mcp_client.side_effect = side_effect

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


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
        vol.Invalid, match=re.escape("required key not provided @ data['query']")
    ):
        tool.parameters({})
    assert tool.parameters({"query": "frogs"}) == {"query": "frogs"}

    tool = api_instance.tools[1]
    assert tool.name == "save_memory"
    assert tool.description == "Save a memory context."
    with pytest.raises(
        vol.Invalid, match=re.escape("required key not provided @ data['context']")
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
        "homeassistant.components.mcp.coordinator.convert_to_voluptuous",
        side_effect=ValueError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
