"""The Model Context Protocol Server implementation using FastMCP."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from mcp import types  # type: ignore[import-untyped]
from mcp.server.auth.provider import TokenVerifier  # type: ignore[import-untyped]
from mcp.server.auth.settings import AuthSettings  # type: ignore[import-untyped]
from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
import voluptuous as vol  # type: ignore[import-untyped]
from voluptuous_openapi import convert  # type: ignore[import-untyped]

from homeassistant.core import HomeAssistant  # type: ignore[import-untyped]
from homeassistant.exceptions import HomeAssistantError  # type: ignore[import-untyped]
from homeassistant.helpers import llm  # type: ignore[import-untyped]

from .const import DOMAIN, STATELESS_LLM_API

_LOGGER = logging.getLogger(__name__)


def _format_tool(tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None) -> types.Tool:
    """Format an LLM tool specification into an MCP tool."""

    input_schema = convert(tool.parameters, custom_serializer=custom_serializer)
    return types.Tool(
        name=tool.name,
        description=tool.description or "",
        inputSchema={
            "type": "object",
            "properties": input_schema["properties"],
        },
    )


def _initialize_fastmcp(
    auth_settings: AuthSettings | None,
    token_verifier: TokenVerifier | None,
) -> FastMCP[Any]:
    """Create the FastMCP server with Home Assistant specific defaults."""

    fastmcp_kwargs: dict[str, Any] = {}
    if auth_settings is not None and token_verifier is not None:
        fastmcp_kwargs["auth"] = auth_settings
        fastmcp_kwargs["token_verifier"] = token_verifier

    return FastMCP[Any](
        name="home-assistant",
        mount_path=f"/{DOMAIN}",
        sse_path="/sse",
        message_path="/messages",
        streamable_http_path="/mcp",
        json_response=False,
        stateless_http=False,
        **fastmcp_kwargs,
    )


async def create_server(
    hass: HomeAssistant,
    llm_api_id: str | list[str],
    llm_context: llm.LLMContext,
    *,
    auth_settings: AuthSettings | None = None,
    token_verifier: TokenVerifier | None = None,
) -> FastMCP[Any]:
    """Create a new Model Context Protocol FastMCP server."""

    if llm_api_id == STATELESS_LLM_API:
        llm_api_id = llm.LLM_API_ASSIST

    server = _initialize_fastmcp(auth_settings, token_verifier)

    async def get_api_instance() -> llm.APIInstance:
        """Get the LLM API instance configured for the MCP server."""

        return await llm.async_get_api(hass, llm_api_id, llm_context)

    base_server = server._mcp_server  # noqa: SLF001 - intentional bridging to low-level server

    try:
        mcp_version = await hass.async_add_executor_job(version, "mcp")
    except PackageNotFoundError:  # pragma: no cover - defensive
        mcp_version = None

    if mcp_version:
        base_server.version = mcp_version

    @base_server.list_prompts()  # type: ignore[no-untyped-call, misc]
    async def handle_list_prompts() -> list[types.Prompt]:
        llm_api = await get_api_instance()
        return [
            types.Prompt(
                name=llm_api.api.name,
                description=f"Default prompt for Home Assistant {llm_api.api.name} API",
            )
        ]

    @base_server.get_prompt()  # type: ignore[no-untyped-call, misc]
    async def handle_get_prompt(
        name: str,
        arguments: dict[str, str] | None,
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

    @base_server.list_tools()  # type: ignore[no-untyped-call, misc]
    async def list_tools() -> list[types.Tool]:
        llm_api = await get_api_instance()
        return [_format_tool(tool, llm_api.custom_serializer) for tool in llm_api.tools]

    @base_server.call_tool()  # type: ignore[misc]
    async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[types.TextContent]:
        llm_api = await get_api_instance()
        tool_input = llm.ToolInput(tool_name=name, tool_args=arguments)
        _LOGGER.debug("Tool call: %s(%s)", tool_input.tool_name, tool_input.tool_args)

        try:
            tool_response = await llm_api.async_call_tool(tool_input)
        except (HomeAssistantError, vol.Invalid) as err:
            raise HomeAssistantError(f"Error calling tool: {err}") from err

        return [
            types.TextContent(
                type="text",
                text=json.dumps(tool_response),
            )
        ]

    return server
