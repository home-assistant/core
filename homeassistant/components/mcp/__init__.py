"""The Model Context Protocol integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from mcp import types
import voluptuous as vol

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


# XXX: Swap in voluptuous-openapi https://github.com/home-assistant-libs/voluptuous-openapi/pull/40
def _convert_schema(input_schema: dict[str, Any]) -> vol.Schema:
    """Format a tool for the API."""
    if input_schema.get("type") != "object":
        raise ValueError("Input schema must be an object.")
    required = set(input_schema.get("required", []))
    fields = {}
    for field_name, properties in input_schema.get("properties", {}).items():
        field_type: type[vol.Required | vol.Optional]
        if field_name in required:
            field_type = vol.Required
        else:
            field_type = vol.Optional
        field_key = field_type(field_name, description=properties.get("description"))
        field_value: Any
        if properties["type"] == "string":
            field_value = str
        elif properties["type"] == "number":
            field_value = float
        elif properties["type"] == "integer":
            field_value = int
        elif properties["type"] == "boolean":
            field_value = bool
        elif properties["type"] == "object":
            field_value = _convert_schema(properties)
        else:
            raise ValueError(f"Unsupported type {properties['type']}")
        fields[field_key] = field_value
    return vol.Schema(fields)


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
        self.parameters = _convert_schema(tool.inputSchema)
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

    # def __init__(self, hass: HomeAssistant, id: str, name: str, coordinator: ModelContextProtocolCoordinator):
    #     """Initialize the API."""
    #     super().__init__(hass=hass, id=id, name=name)
    #     self.coordinator = coordinator

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
