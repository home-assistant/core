"""Tests for the MCP server adapter layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from mcp import types
import pytest
import voluptuous as vol

from homeassistant.components.mcp_server.server import (
    _async_call_tool,
    _async_get_prompt,
    _async_list_prompts,
    _async_list_tools,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType


class _TestTool(llm.Tool):
    """Simple tool used to exercise MCP tool formatting."""

    def __init__(
        self,
        name: str = "TestTool",
        description: str | None = "Test tool description",
        parameters: vol.Schema | None = None,
    ) -> None:
        """Initialize the test tool."""
        self.name = name
        self.description = description
        self.parameters = parameters or vol.Schema({vol.Required("name"): str})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Call the tool."""
        raise NotImplementedError


class _FakeAPIInstance(llm.APIInstance):
    """Test double for an LLM API instance."""

    def __init__(self) -> None:
        """Initialize the fake API instance."""
        api = Mock()
        api.name = "Assist"
        super().__init__(
            api=api,
            api_prompt="Prompt body",
            llm_context=llm.LLMContext(
                platform="mcp_server",
                context=None,
                language="en",
                assistant=None,
                device_id=None,
            ),
            tools=[_TestTool()],
            custom_serializer=None,
        )
        self.async_call_tool_mock: AsyncMock = AsyncMock()

    async def async_call_tool(self, tool_input: llm.ToolInput) -> JsonObjectType:
        """Call the configured mock tool handler."""
        return await self.async_call_tool_mock(tool_input)


@pytest.fixture
def llm_api() -> _FakeAPIInstance:
    """Return a test LLM API instance."""
    return _FakeAPIInstance()


async def test_list_prompts(llm_api: _FakeAPIInstance) -> None:
    """Test listing prompts returns the selected LLM API prompt."""
    prompts = await _async_list_prompts(llm_api)

    assert prompts == [
        types.Prompt(
            name="Assist",
            description="Default prompt for Home Assistant Assist API",
        )
    ]


async def test_get_prompt(llm_api: _FakeAPIInstance) -> None:
    """Test getting a prompt returns the API prompt content."""
    prompt = await _async_get_prompt(llm_api, "Assist", None)

    assert prompt == types.GetPromptResult(
        description="Default prompt for Home Assistant Assist API",
        messages=[
            types.PromptMessage(
                role="assistant",
                content=types.TextContent(type="text", text="Prompt body"),
            )
        ],
    )


async def test_list_tools(llm_api: _FakeAPIInstance) -> None:
    """Test listing tools formats tool metadata for MCP."""
    tools = await _async_list_tools(llm_api)

    assert tools == [
        types.Tool(
            name="TestTool",
            description="Test tool description",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        )
    ]


async def test_call_tool(llm_api: _FakeAPIInstance) -> None:
    """Test calling a tool serializes the tool response."""
    llm_api.async_call_tool_mock.return_value = {"message": "done"}

    result = await _async_call_tool(llm_api, "TestTool", {"name": "kitchen"})

    llm_api.async_call_tool_mock.assert_awaited_once()
    assert llm_api.async_call_tool_mock.await_args is not None
    tool_input = llm_api.async_call_tool_mock.await_args.args[0]
    assert tool_input.tool_name == "TestTool"
    assert tool_input.tool_args == {"name": "kitchen"}
    assert result == [types.TextContent(type="text", text='{"message": "done"}')]


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (HomeAssistantError("boom"), "Error calling tool: boom"),
        (vol.Invalid("bad arguments"), "Error calling tool: bad arguments"),
    ],
)
async def test_call_tool_error(
    llm_api: _FakeAPIInstance, error: Exception, message: str
) -> None:
    """Test calling a tool preserves the current adapter error behavior."""
    llm_api.async_call_tool_mock.side_effect = error

    with pytest.raises(HomeAssistantError, match=message):
        await _async_call_tool(llm_api, "TestTool", {"name": "kitchen"})
