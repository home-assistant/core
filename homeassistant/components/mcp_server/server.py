"""The Model Context Protocol Server implementation.

The Model Context Protocol python sdk defines a Server API that provides the
MCP message handling logic and error handling. The server implementation provided
here is independent of the lower level transport protocol.

See https://modelcontextprotocol.io/docs/concepts/architecture#implementation-example
"""

from collections.abc import Awaitable, Callable, Sequence
from hashlib import blake2s
import json
import logging
from typing import Any

from mcp import types
from mcp.server import Server
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

from .const import STATELESS_LLM_API

_LOGGER = logging.getLogger(__name__)
_MCP_TOOL_NAME_MAX_LENGTH = 64
_MCP_TOOL_NAME_HASH_BYTES = 4


def _format_tool(
    name: str, tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> types.Tool:
    """Format tool specification."""
    input_schema = convert(tool.parameters, custom_serializer=custom_serializer)
    return types.Tool(
        name=name,
        description=tool.description or "",
        inputSchema={
            "type": "object",
            "properties": input_schema["properties"],
        },
    )


def _get_mcp_tool_name(tool_name: str, collision_index: int = 0) -> str:
    """Return an MCP-compatible tool name that handles truncation and collisions."""
    if len(tool_name) <= _MCP_TOOL_NAME_MAX_LENGTH:
        return tool_name

    digest_input = f"{tool_name}:{collision_index}"
    digest = blake2s(
        digest_input.encode(), digest_size=_MCP_TOOL_NAME_HASH_BYTES
    ).hexdigest()
    prefix_length = _MCP_TOOL_NAME_MAX_LENGTH - (_MCP_TOOL_NAME_HASH_BYTES * 2) - 1
    return f"{tool_name[:prefix_length]}_{digest}"


def _get_exposed_tool_names(tools: list[llm.Tool]) -> dict[str, str]:
    """Return a mapping of exposed MCP tool names to their underlying tool names."""
    exposed_names: dict[str, str] = {}

    for tool in tools:
        collision_index = 0
        while True:
            mcp_tool_name = _get_mcp_tool_name(tool.name, collision_index)
            if mcp_tool_name not in exposed_names:
                exposed_names[mcp_tool_name] = tool.name
                break

            if exposed_names[mcp_tool_name] == tool.name:
                _LOGGER.warning(
                    "Skipping duplicate MCP tool name %s for tool %s",
                    mcp_tool_name,
                    tool.name,
                )
                break

            collision_index += 1

    return exposed_names


class _McpTools:
    """Cache MCP tool aliases for a server session."""

    def __init__(
        self, get_api_instance: Callable[[], Awaitable[llm.APIInstance]]
    ) -> None:
        """Initialize the MCP tool cache."""
        self._get_api_instance = get_api_instance
        self._tool_name_by_alias: dict[str, str] = {}
        self._alias_by_tool_name: dict[str, str] = {}
        self._tool_signature: tuple[str, ...] | None = None

    def _refresh(self, tools: list[llm.Tool]) -> None:
        """Refresh cached aliases if the tool set changed."""
        current_signature = tuple(tool.name for tool in tools)
        if self._tool_signature == current_signature:
            return

        self._tool_name_by_alias = _get_exposed_tool_names(tools)
        self._alias_by_tool_name = {
            tool_name: alias
            for alias, tool_name in self._tool_name_by_alias.items()
        }
        self._tool_signature = current_signature

    async def async_list_tools(self) -> list[types.Tool]:
        """Return MCP-formatted tools for the current API instance."""
        llm_api = await self._get_api_instance()
        self._refresh(llm_api.tools)

        listed_tool_names: set[str] = set()
        formatted_tools: list[types.Tool] = []
        for tool in llm_api.tools:
            if tool.name in listed_tool_names:
                continue

            listed_tool_names.add(tool.name)
            formatted_tools.append(
                _format_tool(
                    self._alias_by_tool_name[tool.name],
                    tool,
                    llm_api.custom_serializer,
                )
            )

        return formatted_tools

    async def async_resolve_tool_name(
        self, mcp_tool_name: str
    ) -> tuple[llm.APIInstance, str]:
        """Resolve an MCP tool name to the current Home Assistant tool name."""
        llm_api = await self._get_api_instance()
        self._refresh(llm_api.tools)
        return llm_api, self._tool_name_by_alias.get(mcp_tool_name, mcp_tool_name)


async def create_server(
    hass: HomeAssistant, llm_api_id: str | list[str], llm_context: llm.LLMContext
) -> Server:
    """Create a new Model Context Protocol Server.

    A Model Context Protocol Server object is associated with a single session.
    The MCP SDK handles the details of the protocol.
    """
    if llm_api_id == STATELESS_LLM_API:
        llm_api_id = llm.LLM_API_ASSIST

    server = Server[Any]("home-assistant")

    async def get_api_instance() -> llm.APIInstance:
        """Get the LLM API selected."""
        # Backwards compatibility with old MCP Server config
        return await llm.async_get_api(hass, llm_api_id, llm_context)

    mcp_tools = _McpTools(get_api_instance)

    @server.list_prompts()  # type: ignore[no-untyped-call,untyped-decorator]
    async def handle_list_prompts() -> list[types.Prompt]:
        llm_api = await get_api_instance()
        return [
            types.Prompt(
                name=llm_api.api.name,
                description=f"Default prompt for Home Assistant {llm_api.api.name} API",
            )
        ]

    @server.get_prompt()  # type: ignore[no-untyped-call,untyped-decorator]
    async def handle_get_prompt(
        name: str, arguments: dict[str, str] | None
    ) -> types.GetPromptResult:
        llm_api = await get_api_instance()
        if name != llm_api.api.name:
            raise ValueError(f"Unknown prompt: {name}")

        return types.GetPromptResult(
            description=f"Default prompt for Home Assistant {llm_api.api.name} API",
            messages=[
                types.PromptMessage(
                    role="assistant",
                    content=types.TextContent(
                        type="text",
                        text=llm_api.api_prompt,
                    ),
                )
            ],
        )

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[types.Tool]:
        """List available MCP tools for the selected LLM API."""
        return await mcp_tools.async_list_tools()

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict) -> Sequence[types.TextContent]:
        """Handle calling tools."""
        llm_api, tool_name = await mcp_tools.async_resolve_tool_name(name)
        tool_input = llm.ToolInput(
            tool_name=tool_name,
            tool_args=arguments,
        )
        _LOGGER.debug("Tool call: %s(%s)", tool_input.tool_name, tool_input.tool_args)

        try:
            tool_response = await llm_api.async_call_tool(tool_input)
        except (HomeAssistantError, vol.Invalid) as e:
            raise HomeAssistantError(f"Error calling tool: {e}") from e
        return [
            types.TextContent(
                type="text",
                text=json.dumps(tool_response, ensure_ascii=False),
            )
        ]

    return server
