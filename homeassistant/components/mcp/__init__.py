"""The Model Context Protocol integration."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from mcp import types
from voluptuous_openapi import convert_to_voluptuous

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN
from .coordinator import ModelContextProtocolCoordinator
from .types import ModelContextProtocolConfigEntry

__all__ = [
    "DOMAIN",
    "async_setup_entry",
    "async_unload_entry",
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ModelContextProtocolConfigEntry
) -> bool:
    """Set up Model Context Protocol from a config entry."""
    coordinator = ModelContextProtocolCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    unsub = llm.async_register_api(
        hass,
        ModelContextProtocolAPI(
            hass=hass,
            id=f"{DOMAIN}-{entry.entry_id}",
            name=entry.title,
            coordinator=coordinator,
        ),
    )
    entry.async_on_unload(unsub)

    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.close)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ModelContextProtocolConfigEntry
) -> bool:
    """Unload a config entry."""
    return True


API_PROMPT = "The following tools are available from a remote server named {name}."


class ModelContextProtocolTool(llm.Tool):
    """A Tool exposed over the Model Context Protocol."""

    def __init__(
        self,
        tool: types.Tool,
        coordinator: ModelContextProtocolCoordinator,
    ) -> None:
        """Initialize the tool."""
        self.name = tool.name
        self.description = tool.description
        self.parameters = convert_to_voluptuous(tool.inputSchema)
        self.coordinator = coordinator

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Call the tool."""
        session = self.coordinator.session
        try:
            result = await session.call_tool(tool_input.tool_name, tool_input.tool_args)
        except httpx.HTTPStatusError as error:
            raise HomeAssistantError(f"Error when calling tool: {error}") from error
        return result.model_dump(exclude_unset=True, exclude_none=True)


@dataclass(kw_only=True)
class ModelContextProtocolAPI(llm.API):
    """Define an object to hold the Model Context Protocol API."""

    coordinator: ModelContextProtocolCoordinator

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        tools: list[llm.Tool] = [
            ModelContextProtocolTool(tool, self.coordinator)
            for tool in self.coordinator.data
        ]
        return llm.APIInstance(
            self,
            API_PROMPT.format(name=self.name),
            llm_context,
            tools=tools,
        )
