"""The Model Context Protocol Server implementation.

The Model Context Protocol python sdk defines a Server API that provides the
MCP message handling logic and error handling. The server implementation provided
here is independent of the lower level transport protocol.

See https://modelcontextprotocol.io/docs/concepts/architecture#implementation-example
"""

from collections.abc import Callable
from dataclasses import replace
import json
import logging
from typing import Any, cast

from mcp import types
from mcp.server import Server, ServerRequestContext
import probatio

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.network import get_url

from .const import STATELESS_LLM_API

_LOGGER = logging.getLogger(__name__)

SNAPSHOT_RESOURCE_URI = "homeassistant://assist/context-snapshot"
SNAPSHOT_RESOURCE_MIME_TYPE = "text/plain"
LIVE_CONTEXT_TOOL_NAME = "homeassistant__GetLiveContext"
META_DEVICE_ID = "io.home-assistant/device_id"


def _has_live_context_tool(llm_api: llm.APIInstance) -> bool:
    """Return if the selected API exposes the live context tool."""
    return any(tool.name == LIVE_CONTEXT_TOOL_NAME for tool in llm_api.tools)


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> types.Tool:
    """Format tool specification."""
    input_schema = probatio.to_openapi(
        tool.parameters,
        custom_serializer=custom_serializer,
        openapi_version="3.1.0",
    )
    mcp_schema: dict[str, Any] = {
        "type": "object",
        "properties": input_schema["properties"],
    }
    # Omitted by to_openapi when the tool has no required parameters.
    if required := input_schema.get("required"):
        mcp_schema["required"] = required
    return types.Tool(
        name=tool.name,
        title=tool.title,
        description=tool.description or "",
        input_schema=mcp_schema,
        annotations=types.ToolAnnotations(
            read_only_hint=tool.annotations.read_only,
            destructive_hint=tool.annotations.destructive,
            idempotent_hint=tool.annotations.idempotent,
            open_world_hint=tool.annotations.open_world,
        ),
    )


async def create_server(
    hass: HomeAssistant,
    llm_api_id: str | list[str],
    llm_context: llm.LLMContext,
    read_only: bool,
) -> Server:
    """Create a new Model Context Protocol Server.

    A Model Context Protocol Server object is associated with a single session.
    The MCP SDK handles the details of the protocol.
    """
    if llm_api_id == STATELESS_LLM_API:
        llm_api_id = llm.LLM_API_ASSIST

    async def get_api_instance(ctx: ServerRequestContext[Any]) -> llm.APIInstance:
        """Get the LLM API selected."""
        device_id = ctx.meta.get(META_DEVICE_ID) if ctx.meta else None
        if device_id is not None and not isinstance(device_id, str):
            raise ValueError(f"{META_DEVICE_ID} must be a string")

        # Backwards compatibility with old MCP Server config
        llm_api = await llm.async_get_api(
            hass, llm_api_id, replace(llm_context, device_id=device_id)
        )
        if read_only:
            # Removing the tools also blocks calls to them.
            llm_api.tools = [
                tool for tool in llm_api.tools if tool.annotations.read_only
            ]
        return llm_api

    async def handle_list_prompts(
        ctx: ServerRequestContext[Any],
        params: types.PaginatedRequestParams | None = None,
    ) -> types.ListPromptsResult:
        llm_api = await get_api_instance(ctx)
        return types.ListPromptsResult(
            prompts=[
                types.Prompt(
                    name=llm_api.api.name,
                    description=f"Default prompt for Home Assistant {llm_api.api.name} API",
                )
            ]
        )

    async def handle_get_prompt(
        ctx: ServerRequestContext[Any],
        params: types.GetPromptRequestParams,
    ) -> types.GetPromptResult:
        llm_api = await get_api_instance(ctx)
        if params.name != llm_api.api.name:
            raise ValueError(f"Unknown prompt: {params.name}")

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

    async def handle_list_resources(
        ctx: ServerRequestContext[Any],
        params: types.PaginatedRequestParams | None = None,
    ) -> types.ListResourcesResult:
        llm_api = await get_api_instance(ctx)
        if not _has_live_context_tool(llm_api):
            return types.ListResourcesResult(resources=[])

        return types.ListResourcesResult(
            resources=[
                types.Resource(
                    uri=SNAPSHOT_RESOURCE_URI,
                    name="assist_context_snapshot",
                    title="Assist context snapshot",
                    description=(
                        "A snapshot of the current Assist context, matching the"
                        " existing homeassistant__GetLiveContext tool output."
                    ),
                    mime_type=SNAPSHOT_RESOURCE_MIME_TYPE,
                )
            ]
        )

    async def handle_read_resource(
        ctx: ServerRequestContext[Any],
        params: types.ReadResourceRequestParams,
    ) -> types.ReadResourceResult:
        uri = params.uri
        if str(uri) != SNAPSHOT_RESOURCE_URI:
            raise ValueError(f"Unknown resource: {uri}")

        llm_api = await get_api_instance(ctx)
        if not _has_live_context_tool(llm_api):
            raise ValueError(f"Unknown resource: {uri}")

        tool_response = await llm_api.async_call_tool(
            llm.ToolInput(tool_name=LIVE_CONTEXT_TOOL_NAME, tool_args={})
        )
        if tool_response.error:
            raise HomeAssistantError(cast(str, tool_response.data["error"]))

        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=SNAPSHOT_RESOURCE_URI,
                    mime_type=SNAPSHOT_RESOURCE_MIME_TYPE,
                    text=cast(str, tool_response.data["result"]),
                )
            ]
        )

    async def list_tools(
        ctx: ServerRequestContext[Any],
        params: types.PaginatedRequestParams | None = None,
    ) -> types.ListToolsResult:
        """List available time tools."""
        llm_api = await get_api_instance(ctx)
        return types.ListToolsResult(
            tools=[
                _format_tool(tool, llm_api.custom_serializer) for tool in llm_api.tools
            ]
        )

    async def call_tool(
        ctx: ServerRequestContext[Any],
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        """Handle calling tools."""
        llm_api = await get_api_instance(ctx)
        tool_input = llm.ToolInput(
            tool_name=params.name, tool_args=params.arguments or {}
        )
        _LOGGER.debug("Tool call: %s(%s)", tool_input.tool_name, tool_input.tool_args)

        try:
            tool_response = await llm_api.async_call_tool(tool_input)
        except (HomeAssistantError, probatio.Invalid) as e:
            return types.CallToolResult(
                content=[
                    types.TextContent(type="text", text=f"Error calling tool: {e}")
                ],
                is_error=True,
            )
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(tool_response.data, ensure_ascii=False),
                )
            ],
            is_error=tool_response.error,
        )

    return Server[Any](
        name="home-assistant",
        icons=[
            types.Icon(
                src=f"{get_url(hass, require_current_request=True)}/static/icons/favicon-192x192.png",
                mime_type="image/png",
                sizes=["192x192"],
            )
        ],
        on_list_prompts=handle_list_prompts,
        on_get_prompt=handle_get_prompt,
        on_list_resources=handle_list_resources,
        on_read_resource=handle_read_resource,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )
