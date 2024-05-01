"""Module to coordinate llm tools."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cached_property
import logging
from types import FunctionType
from typing import Any

import voluptuous as vol
from voluptuous_openapi import UNSUPPORTED, convert

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from . import area_registry as ar, config_validation as cv, floor_registry as fr, intent

_LOGGER = logging.getLogger(__name__)

DATA_KEY = "llm_tool"


def default_custom_serializer(schema: Any) -> Any:
    """Serialize additional types in OpenAPI-compatible format."""
    from homeassistant.util.color import (  # pylint: disable=import-outside-toplevel
        color_name_to_rgb,
    )

    if schema is cv.string:
        return {"type": "string"}

    if schema is cv.boolean:
        return {"type": "boolean"}

    if schema is color_name_to_rgb:
        return {"type": "string"}

    if isinstance(schema, cv.multi_select):
        return {"enum": schema.options}

    if isinstance(schema, FunctionType):
        return {}

    return UNSUPPORTED


@dataclass(slots=True)
class ToolInput:
    """Tool input to be processed."""

    tool_name: str
    tool_args: dict[str, Any]
    platform: str
    context: Context | None
    user_prompt: str | None
    language: str | None
    agent_id: str | None
    conversation_id: str | None
    device_id: str | None
    assistant: str | None


class Tool:
    """LLM Tool base class."""

    name: str
    description: str
    parameters: vol.Schema
    custom_serializer: Callable[[Any], Any]

    def __init__(
        self,
        name: str,
        description: str,
        parameters: vol.Schema = vol.Schema({}),
        custom_serializer: Callable[[Any], Any] = default_custom_serializer,
    ) -> None:
        """Init the class."""
        self.name = name
        self.description = description
        self.parameters = parameters
        self.custom_serializer = custom_serializer

    @cached_property
    def specification(self) -> dict[str, Any]:
        """Get the tool specification in OpenAPI-compatible format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": convert(
                self.parameters, custom_serializer=self.custom_serializer
            ),
        }

    @abstractmethod
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput) -> Any:
        """Call the tool."""
        raise NotImplementedError

    def as_dict(self) -> dict[str, Any]:
        """Get the tool specification in OpenAPI-compatible format."""
        return self.specification

    def __repr__(self) -> str:
        """Represent a string of a Tool."""
        return f"<{self.__class__.__name__} - {self.name}>"


@callback
def async_register_tool(hass: HomeAssistant, tool: Tool) -> None:
    """Register an LLM tool with Home Assistant."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        tools = hass.data[DATA_KEY] = {}

    if tool.name in tools:
        raise HomeAssistantError(f"Tool {tool.name} is already registered")

    tools[tool.name] = tool


@callback
def async_remove_tool(hass: HomeAssistant, tool_name: str) -> None:
    """Remove an LLM tool from Home Assistant."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        return

    tools.pop(tool_name, None)


@callback
def async_get_tools(hass: HomeAssistant) -> Iterable[Tool]:
    """Return a list of registered LLM tools."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        tools = {}

    return tools.values()


@callback
async def async_call_tool(hass: HomeAssistant, tool_input: ToolInput) -> Any:
    """Call a LLM tool, validate args and return the response."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        tools = {}

    tool = tools[tool_input.tool_name]

    if tool_input.context is None:
        tool_input.context = Context()

    tool_input.tool_args = tool.parameters(tool_input.tool_args)

    return await tool.async_call(hass, tool_input)


class IntentTool(Tool):
    """LLM Tool representing an Intent."""

    def __init__(
        self,
        intent_type: str,
        slot_schema: vol.Schema | None = None,
    ) -> None:
        """Init the class."""
        if slot_schema is None:
            slot_schema = vol.Schema({})
        super().__init__(
            intent_type,
            f"Execute Home Assistant {intent_type} intent",
            slot_schema,
        )

    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput) -> Any:
        """Handle the intent."""
        slots = {key: {"value": val} for key, val in tool_input.tool_args.items()}

        if "area" in slots:
            areas = ar.async_get(hass)
            id_or_name = slots["area"]["value"]

            area = areas.async_get_area(id_or_name) or areas.async_get_area_by_name(
                id_or_name
            )
            if not area:
                # Check area aliases
                for maybe_area in areas.areas.values():
                    if not maybe_area.aliases:
                        continue

                    for area_alias in maybe_area.aliases:
                        if id_or_name == area_alias.casefold():
                            area = maybe_area
                            break
            if area:
                slots["area"]["value"] = area.id
                slots["area"]["text"] = area.name
            else:
                slots["area"]["text"] = id_or_name

        if "floor" in slots:
            floors = fr.async_get(hass)
            id_or_name = slots["floor"]["value"]

            floor = floors.async_get_floor(
                id_or_name
            ) or floors.async_get_floor_by_name(id_or_name)
            if not floor:
                # Check floor aliases
                for maybe_floor in floors.floors.values():
                    if not maybe_floor.aliases:
                        continue

                    for floor_alias in maybe_floor.aliases:
                        if id_or_name == floor_alias.casefold():
                            floor = maybe_floor
                            break
            if floor:
                slots["floor"]["value"] = floor.floor_id
                slots["floor"]["text"] = floor.name
            else:
                slots["floor"]["text"] = id_or_name

        intent_response = await intent.async_handle(
            hass,
            tool_input.platform,
            self.name,
            slots,
            tool_input.user_prompt,
            tool_input.context,
            tool_input.language,
            tool_input.assistant,
        )
        return intent_response.as_dict()
