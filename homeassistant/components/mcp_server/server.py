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
from mcp.server.lowlevel.helper_types import ReadResourceContents
from pydantic import AnyUrl
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.conversation import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.util import yaml as yaml_util

from .const import STATELESS_LLM_API

_LOGGER = logging.getLogger(__name__)

EXPOSED_ENTITIES_RESOURCE_URI = "homeassistant://assist/exposed-entities"
EXPOSED_ENTITIES_RESOURCE_URL = AnyUrl(EXPOSED_ENTITIES_RESOURCE_URI)
EXPOSED_ENTITIES_RESOURCE_MIME_TYPE = "text/yaml"


def _exposed_entities_resource_supported(
    llm_api_id: str | list[str], assistant: str | None
) -> bool:
    """Return if the Assist exposed entities resource should be available."""
    if assistant is None:
        return False

    if isinstance(llm_api_id, str):
        llm_api_ids = [llm_api_id]
    else:
        llm_api_ids = llm_api_id

    return llm.LLM_API_ASSIST in llm_api_ids


def _get_exposed_entities_resource_contents(hass: HomeAssistant, assistant: str) -> str:
    """Build model-friendly exposed entity context for the MCP resource."""
    exposed_entities = llm.async_get_exposed_entities(
        hass, assistant, include_state=True
    )
    entities = [
        {"entity_id": entity_id, **entity_info}
        for domain in (CALENDAR_DOMAIN, SCRIPT_DOMAIN, "entities")
        for entity_id, entity_info in exposed_entities[domain].items()
    ]
    entities.sort(key=lambda item: (item["names"], item["entity_id"]))

    return yaml_util.dump(
        {
            "assistant": assistant,
            "entities": entities,
        }
    )


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
    hass: HomeAssistant, llm_api_id: str | list[str], llm_context: llm.LLMContext
) -> Server:
    """Create a new Model Context Protocol Server.

    A Model Context Protocol Server object is associated with a single session.
    The MCP SDK handles the details of the protocol.
    """
    if llm_api_id == STATELESS_LLM_API:
        llm_api_id = llm.LLM_API_ASSIST

    server = Server[Any]("home-assistant")
    has_exposed_entities_resource = _exposed_entities_resource_supported(
        llm_api_id, llm_context.assistant
    )

    async def get_api_instance() -> llm.APIInstance:
        """Get the LLM API selected."""
        # Backwards compatibility with old MCP Server config
        return await llm.async_get_api(hass, llm_api_id, llm_context)

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

    @server.list_resources()  # type: ignore[no-untyped-call,untyped-decorator]
    async def handle_list_resources() -> list[types.Resource]:
        if not has_exposed_entities_resource:
            return []

        return [
            types.Resource(
                uri=EXPOSED_ENTITIES_RESOURCE_URL,
                name="assist_exposed_entities",
                title="Assist exposed entities",
                description=(
                    "Entities exposed to Assist, including current state and"
                    " a curated set of attributes."
                ),
                mimeType=EXPOSED_ENTITIES_RESOURCE_MIME_TYPE,
            )
        ]

    @server.read_resource()  # type: ignore[no-untyped-call,untyped-decorator]
    async def handle_read_resource(uri: AnyUrl) -> Sequence[ReadResourceContents]:
        if (
            not has_exposed_entities_resource
            or str(uri) != EXPOSED_ENTITIES_RESOURCE_URI
        ):
            raise ValueError(f"Unknown resource: {uri}")

        return [
            ReadResourceContents(
                content=_get_exposed_entities_resource_contents(
                    hass, llm_context.assistant or CONVERSATION_DOMAIN
                ),
                mime_type=EXPOSED_ENTITIES_RESOURCE_MIME_TYPE,
            )
        ]

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[types.Tool]:
        """List available time tools."""
        llm_api = await get_api_instance()
        return [_format_tool(tool, llm_api.custom_serializer) for tool in llm_api.tools]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict) -> Sequence[types.TextContent]:
        """Handle calling tools."""
        llm_api = await get_api_instance()
        tool_input = llm.ToolInput(tool_name=name, tool_args=arguments)
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
