"""The Model Context Protocol Server implementation.

The Model Context Protocol python sdk defines a Server API that provides the
MCP message handling logic and error handling. The server implementation provided
here is independent of the lower level transport protocol.

See https://modelcontextprotocol.io/docs/concepts/architecture#implementation-example
"""

from collections.abc import Callable, Sequence
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

_LOGGER = logging.getLogger(__name__)


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> types.Tool:
    """Format tool specification."""
    input_schema = convert(tool.parameters, custom_serializer=custom_serializer)
    return types.Tool(
        name=tool.name,
        description=tool.description or "",
        inputSchema={
            "type": "object",
            "properties": input_schema["properties"],
        },
    )


async def create_server(
    hass: HomeAssistant, llm_api_id: str, llm_context: llm.LLMContext
) -> Server:
    """Create a new Model Context Protocol Server.

    A Model Context Protocol Server object is associated with a single session.
    The MCP SDK handles the details of the protocol.
    """

    server = Server("home-assistant")

    @server.list_tools()  # type: ignore[no-untyped-call, misc]
    async def list_tools() -> list[types.Tool]:
        """List available time tools."""
        llm_api = await llm.async_get_api(hass, llm_api_id, llm_context)
        return [_format_tool(tool, llm_api.custom_serializer) for tool in llm_api.tools]

    @server.call_tool()  # type: ignore[no-untyped-call, misc]
    async def call_tool(name: str, arguments: dict) -> Sequence[types.TextContent]:
        """Handle calling tools."""
        llm_api = await llm.async_get_api(hass, llm_api_id, llm_context)
        tool_input = llm.ToolInput(tool_name=name, tool_args=arguments)
        _LOGGER.debug("Tool call: %s(%s)", tool_input.tool_name, tool_input.tool_args)

        try:
            tool_response = await llm_api.async_call_tool(tool_input)
        except (HomeAssistantError, vol.Invalid) as e:
            raise HomeAssistantError(f"Error calling tool: {e}") from e
        return [
            types.TextContent(
                type="text",
                text=json.dumps(tool_response),
            )
        ]

    return server
